"""
run and check CLI subcommands
"""
from __future__ import annotations

import concurrent.futures
import getpass
import os
import random
import socket
import sys
import time
from distutils.util import strtobool
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING

import ansible_runner
import click
from boardwalkd.protocol import (
    WorkspaceClient,
    WorkspaceDetails,
    WorkspaceEvent,
    WorkspaceHasMutex,
)
from tornado.httpclient import HTTPClientError
from tornado.simple_httpclient import HTTPTimeoutError

from boardwalk.ansible import (
    ansible_inventory,
    ansible_runner_errors_to_output,
    AnsibleRunError,
    AnsibleRunnerBaseException,
    AnsibleRunnerFailedHost,
    AnsibleRunnerGeneralError,
    AnsibleRunnerUnreachableHost,
)
from boardwalk.app_exceptions import BoardwalkException
from boardwalk.host import Host, RemoteHostLocked
from boardwalk.log import boardwalk_logger
from boardwalk.manifest import get_boardwalkd_url, get_ws, NoActiveWorkspace, Workspace
from boardwalk.state import RemoteStateModel, RemoteStateWorkflow, RemoteStateWorkspace

if TYPE_CHECKING:
    from typing import ItemsView

    from boardwalk.ansible import HostVarsType, InventoryHostVars


become_password: str | None = None
boardwalkd_client: WorkspaceClient | None = None
boardwalkd_send_broadcasts: bool = False
_check_mode: bool = True
_stomp_locks: bool = False


@click.command("run", short_help="Runs workflow jobs")
@click.option(
    "--ask-become-pass/--no-ask-become-pass",
    "-K/-nK",
    help="Whether or not ask for a become password. The ANSIBLE_BECOME_ASK_PASS env var can also set this",
    default=False,
    show_default=True,
)
@click.option(
    "--check/--no-check",
    "-C/-nC",
    help="Whether or not to run Ansible in --check/-C mode",
    default=False,
    show_default=True,
)
@click.option(
    "--limit",
    "-l",
    help="An Ansible pattern to limit hosts by. Defaults to no limit",
    default="",
)
@click.option(
    "--server-connect/--no-server-connect",
    "-sc/-nsc",
    help=(
        "Whether or not connect to the configured boardwalkd server, if any."
        " It may be dangerous to run workflows without connecting to the server"
    ),
    default=True,
    show_default=True,
)
@click.option(
    "--sort-hosts",
    "-s",
    help="Overrides the workspace's default sort ordering. May be specified with first letter",
    type=click.Choice(
        ["shuffle", "s", "ascending", "a", "descending", "d", ""], case_sensitive=False
    ),
    default="",
)
@click.option(
    "--stomp-locks/--no-stomp-locks",
    help="Whether or not to ignore and override existing host locks. Probably dangerous",
    default=False,
    show_default=True,
)
@click.pass_context
def run(
    ctx: click.Context,
    ask_become_pass: bool,
    check: bool,
    limit: str,
    server_connect: bool,
    sort_hosts: str,
    stomp_locks: bool,
):
    """
    Runs workflow jobs defined in the Boardwalkfile.py
    """
    # Set globals from CLI options
    global _check_mode
    _check_mode = check
    global _stomp_locks
    _stomp_locks = stomp_locks

    try:
        ws = get_ws()
    except NoActiveWorkspace as e:
        raise BoardwalkException(e.message)
    boardwalk_logger.info(f"Using workspace: {ws.name}")

    # See if we have any hosts
    if len(ws.state.hosts) == 0:
        raise BoardwalkException(
            "No hosts found in state. Have you run `boardwalk init`?"
        )

    # Check if a --limit is required for this Workspace
    if ws.cfg.require_limit and not limit:
        raise BoardwalkException("Workspace requires the --limit option be supplied")

    # If no limit is supplied, then the limit is effectively "all"
    if limit:
        effective_limit = limit
    else:
        effective_limit = "all"

    ws.assert_host_pattern_unchanged()

    # Setup boardwalkd client if configured
    boardwalkd_url = get_boardwalkd_url()
    if boardwalkd_url and server_connect:
        global boardwalkd_client
        boardwalkd_client = WorkspaceClient(boardwalkd_url, ws.name)

    if boardwalkd_client and not _check_mode:
        global boardwalkd_send_broadcasts
        boardwalkd_send_broadcasts = True

    if boardwalkd_client:
        bootstrap_with_server(ws, ctx)

    # Lock the local Workspace
    ws.mutex()
    ctx.call_on_close(ws.unmutex)

    # Multiplex slow inventory operations
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Process --limit
        filter_hosts_by_limit_future = executor.submit(
            filter_hosts_by_limit, ws, ws.state.hosts.items(), effective_limit
        )
        # Get data for inventory_vars used in Jobs
        inventory_data_future = executor.submit(ansible_inventory)
        try:
            hosts_working_list = filter_hosts_by_limit_future.result()
        except NoHostsMatched:
            raise BoardwalkException(
                (
                    "No host matched the given limit pattern. Ensure the expected"
                    " hosts exist in the Ansible inventory and confirm they were"
                    " reachable during `boardwalk init`"
                )
            )
        inventory_vars = inventory_data_future.result()["_meta"]["hostvars"]

    # Sort hosts
    # If no --sort-hosts override was passed, then use the workspace default
    if not sort_hosts:
        sort_hosts = ws.cfg.default_sort_order
    hosts_working_list = sort_host_list(hosts_working_list, sort_hosts)

    # Check preconditions locally
    hosts_working_list = check_host_preconditions_locally(
        hosts_working_list, inventory_vars, ws
    )
    if len(hosts_working_list) < 1:
        boardwalk_logger.error("No hosts meet preconditions")
        return

    # Get the become password if necessary
    try:
        if ask_become_pass or strtobool(os.environ["ANSIBLE_BECOME_ASK_PASS"]):
            global become_password
            become_password = getpass.getpass("BECOME password: ")
    except ValueError:
        raise BoardwalkException(
            "ANSIBLE_BECOME_ASK_PASS env variable has an invalid boolean value"
        )
    except KeyError:
        pass

    run_workflow(
        hosts=hosts_working_list,
        inventory_vars=inventory_vars,
        workspace=ws,
    )


@click.option(
    "--ask-become-pass/--no-ask-become-pass",
    "-K/-nK",
    help="Whether or not ask for a become password. The ANSIBLE_BECOME_ASK_PASS env var can also set this",
    default=False,
)
@click.option(
    "--limit",
    "-l",
    help="An Ansible pattern to limit hosts by. Defaults to no limit",
    default="",
)
@click.option(
    "--server-connect/--no-server-connect",
    "-sc/-nsc",
    help=(
        "Whether or not connect to the configured boardwalkd server, if any."
        " It may be dangerous to run workflows without connecting to the server"
    ),
    default=True,
    show_default=True,
)
@click.option(
    "--sort-hosts",
    "-s",
    help="Overrides the workspace's default sort ordering. May be specified with first letter",
    type=click.Choice(
        ["shuffle", "s", "ascending", "a", "descending", "d", ""], case_sensitive=False
    ),
    default="",
)
@click.command(
    "check", short_help="Runs workflow in check mode. Equivalent to run --check"
)
@click.pass_context
def check(
    ctx: click.Context,
    ask_become_pass: bool,
    limit: str,
    server_connect: bool,
    sort_hosts: str,
):
    """Runs workflow in check mode. Equivalent to run --check"""
    ctx.invoke(
        run,
        ask_become_pass=ask_become_pass,
        limit=limit,
        server_connect=server_connect,
        sort_hosts=sort_hosts,
        check=True,
    )


def run_workflow(
    hosts: list[Host],
    inventory_vars: HostVarsType,
    workspace: Workspace,
):
    """Runs the workspace's workflow against a list of hosts"""
    i = 0
    while i < len(hosts):
        host = hosts[i]

        boardwalk_logger.info(
            f"{host.name}: Workflow iteration on host {i+1} of {len(hosts)}"
        )
        if boardwalkd_client:
            boardwalkd_client.queue_event(
                WorkspaceEvent(
                    severity="info",
                    message=f"{host.name}: Workflow iteration on host {i+1} of {len(hosts)}",
                ),
            )

        handle_workflow_catch(workspace=workspace, hostname=host.name)

        # Connect to the remote host
        # Wrap everything in try/except so we can handle failures
        try:
            lock_remote_host(host)
            # Wrap everything in a try/finally so we always try to unlock the
            # remote host
            unreachable_exception = None
            try:
                directly_confirm_host_preconditions(
                    host, inventory_vars[host.name], workspace
                )
                execute_host_workflow(host, workspace)
            except AnsibleRunnerUnreachableHost as e:
                unreachable_exception = e
            finally:
                # If the host was unreachable there's no point in trying to recover here
                if unreachable_exception:
                    raise unreachable_exception
                # Finish by releasing the remote lock
                boardwalk_logger.info(f"{host.name}: Release remote host lock")
                if boardwalkd_client:
                    boardwalkd_client.queue_event(
                        WorkspaceEvent(
                            severity="info",
                            message=f"{host.name}: Release remote host lock",
                        ),
                    )
                host.release(become_password=become_password, check=_check_mode)
        except (AnsibleRunnerGeneralError, AnsibleRunError) as e:
            # These errors probably indicate a local issue with Ansible that should
            # caught early, such as syntax errors, so we always bail when encountered
            if boardwalkd_client:
                boardwalkd_client.queue_event(
                    WorkspaceEvent(
                        severity="error",
                        message=f"{host.name}: {e.__class__.__qualname__}",
                    )
                )
            raise BoardwalkException(e.runner_msg)
        except (
            AnsibleRunnerFailedHost,
            AnsibleRunnerUnreachableHost,
            RemoteHostLocked,
        ) as e:
            run_failure_mode_handler(
                exception=e,
                hostname=host.name,
                workspace=workspace,
            )
            continue
        except HostPreConditionsUnmet:
            pass

        i += 1


def run_failure_mode_handler(
    exception: Exception,
    hostname: str,
    workspace: Workspace,
):
    """
    Common failure handler that used in catching exceptions during workflow runs
    """
    if boardwalkd_client:
        if isinstance(exception, AnsibleRunnerBaseException):
            runner_errors = ansible_runner_errors_to_output(
                runner=exception.runner, include_msg=False
            )
            msg = f"{exception.runner_msg}: {runner_errors}"
        else:
            try:
                msg: str = exception.message  # type: ignore
            except AttributeError:
                msg = exception.__class__.__qualname__
        boardwalkd_client.queue_event(
            WorkspaceEvent(
                severity="error",
                message=msg,
            ),
            broadcast=boardwalkd_send_broadcasts,
        )

    boardwalk_logger.error(
        f"{exception}\n{hostname}: Job encountered error; Workspace will catch"
    )
    if boardwalkd_client:
        try:
            boardwalkd_client.post_catch()
        except ConnectionRefusedError:
            boardwalk_logger.error(
                (
                    f"{hostname}: Could not catch Workspace at server because"
                    " connection was refused. Falling back to local catch"
                )
            )
            workspace.catch()
    else:
        workspace.catch()


def filter_hosts_by_limit(
    workspace: Workspace, hosts: ItemsView[str, Host], pattern: str
) -> list[Host]:
    """Accepts a list of host objects and returns a list of object matching a host
    pattern string"""
    boardwalk_logger.info("Reading inventory to process any --limit")
    out, err, rc = ansible_runner.run_command(
        cmdline_args=[
            "--list-hosts",
            workspace.cfg.host_pattern,
            "--limit",
            pattern,
        ],
        envvars={"ANSIBLE_BECOME_ASK_PASS": False},
        executable_cmd="ansible",
        input_fd=sys.stdin,
        project_dir=str(Path.cwd()),
        quiet=True,
        suppress_env_files=True,
    )
    if rc != 0:
        BoardwalkException(f"Failed to process --limit pattern. {err}")

    # Format the output into a clean list
    inventory_host_list = [line.strip() for line in out.splitlines()[1:]]

    # Get the intersection of the list of hosts from the inventory with the
    # hosts present in the state
    hosts_filtered: list[Host] = []
    for hostname, host in hosts:
        if hostname in inventory_host_list:
            hosts_filtered.append(host)
    if len(hosts_filtered) == 0:
        raise NoHostsMatched
    return hosts_filtered


def sort_host_list(hosts: list[Host], sort_method: str):
    """Accepts a list of host objects and return a list of host objects sorted
    by the requested sort method. The acceptable sorting methods are/must be
    defined and validated by the calling click function"""
    if sort_method == "shuffle" or sort_method == "s":
        random.shuffle(hosts)
    elif sort_method == "ascending" or sort_method == "a":
        hosts.sort(key=lambda h: h.name)
    elif sort_method == "descending" or sort_method == "d":
        hosts.sort(key=lambda h: h.name, reverse=True)
    return hosts


def check_host_preconditions_locally(
    hosts: list[Host], inventory_vars: HostVarsType, workspace: Workspace
) -> list[Host]:
    """Checks preconditions of jobs defined in workspace's workflow. Returns
    a list of the hosts that meet preconditions. Prints warnings for hosts that
    don't pass. Preconditions are ignored for hosts that have started a workflow
    but haven't finished"""
    hosts_meeting_preconditions: list[Host] = []
    workflow = workspace.cfg.workflow
    for host in hosts:
        # See if preconditions are met based upon local state
        any_job_preconditions_unmet = False

        if workspace.cfg.workflow.cfg.always_retry_failed_hosts:
            # If the workflow was started but never finished, ignore preconditions
            try:
                boardwalk_state = RemoteStateModel.parse_obj(
                    host.ansible_facts["ansible_local"]["boardwalk_state"]
                )
                if (
                    boardwalk_state.workspaces[workspace.name].workflow.started
                    and not boardwalk_state.workspaces[
                        workspace.name
                    ].workflow.succeeded
                ):
                    hosts_meeting_preconditions.append(host)
                    boardwalk_logger.warn(
                        (
                            f"{host.name}: Host started workflow but never completed."
                            " Job preconditions are ignored for this host"
                        )
                    )
                    continue
            except KeyError:
                pass

        for job in chain(workflow.i_jobs, workflow.i_exit_jobs):
            if not job.preconditions(
                facts=host.ansible_facts, inventory_vars=inventory_vars[host.name]
            ):
                any_job_preconditions_unmet = True
                boardwalk_logger.warn(
                    (
                        f"{host.name}: Job {job.name} preconditions unmet in local state"
                        " and will be skipped. If this is in error, re-run `boardwalk init`"
                    )
                )
        # If any Job preconditions were unmet, then skip this host
        if any_job_preconditions_unmet:
            continue

        hosts_meeting_preconditions.append(host)
    return hosts_meeting_preconditions


def handle_workflow_catch(workspace: Workspace, hostname: str):
    """Handles local and remote workspace catches. Blocks under caught conditions"""
    if workspace.caught():
        boardwalk_logger.info(
            f"{hostname}: The {workspace.name} workspace is locally caught. Waiting for release before continuing..."
        )
        if boardwalkd_client:
            boardwalkd_client.queue_event(
                WorkspaceEvent(
                    severity="info",
                    message=f"{hostname}: Waiting for local worker catch to release",
                ),
            )
        while workspace.caught():
            time.sleep(5)  # nosemgrep: python.lang.best-practice.sleep.arbitrary-sleep

    # Now check if there is a remote catch
    def check_boardwalkd_catch(client: WorkspaceClient) -> bool:
        """
        Wraps catch checking method so that the client can consider the
        remote workspace locked if it can't be reached
        """
        # First check if there is a local catch. This takes precedence over remote catches
        try:
            return client.caught()
        except (ConnectionRefusedError, HTTPTimeoutError):
            boardwalk_logger.error(
                (
                    f"Could not connect to {client.url.geturl()} while checking for remote catch."
                    " Boardwalk considers the remote workspace caught if it can't be reached"
                )
            )
            return True
        except HTTPClientError as e:
            boardwalk_logger.error(
                (
                    f"Received error {e} from {client.url.geturl()} while checking for remote catch."
                    " Boardwalk considers the remote workspace caught if it can't be reached"
                )
            )
            return True

    if boardwalkd_client and check_boardwalkd_catch(boardwalkd_client):
        boardwalk_logger.info(
            (
                f"{hostname}: The {workspace.name} workspace is remotely caught on {boardwalkd_client.url.geturl()}"
                " Waiting for release before continuing"
            )
        )
        boardwalkd_client.queue_event(
            WorkspaceEvent(
                severity="info",
                message=f"{hostname}: Waiting for remote catch to release",
            )
        )
        while check_boardwalkd_catch(boardwalkd_client):
            time.sleep(5)  # nosemgrep: python.lang.best-practice.sleep.arbitrary-sleep


def lock_remote_host(host: Host):
    if boardwalkd_client:
        boardwalkd_client.queue_event(
            WorkspaceEvent(
                severity="info",
                message=f"{host.name}: Locking remote host",
            ),
        )
    host.lock(
        become_password=become_password,
        check=_check_mode,
        stomp_existing_locks=_stomp_locks,
    )


def bootstrap_with_server(workspace: Workspace, ctx: click.Context):
    """Performs all of the initial set-up actions needed when boardwalk is
    configured to connect to a central boardwalkd"""
    if not boardwalkd_client:
        raise BoardwalkException(
            "bootstrap_with_server called but no boardwalkd_client exists"
        )
    boardwalkd_url = boardwalkd_client.url.geturl()
    # Check if the if the Workspace is locked. We don't want to conflict with another worker
    try:
        if boardwalkd_client.has_mutex():
            raise BoardwalkException(
                f"A workspace with the name {workspace.name} has already locked on {boardwalkd_url}"
            )
    except ConnectionRefusedError:
        raise BoardwalkException(f"Could not connect to server {boardwalkd_url}")
    except socket.gaierror:
        raise BoardwalkException(f"Could not resolve server {boardwalkd_url}")
    except HTTPClientError as e:
        raise BoardwalkException(f"Received error {e} from {boardwalkd_url}")

    # Post the worker's details, which also creates the workspace
    try:
        boardwalkd_client.post_details(
            WorkspaceDetails(
                host_pattern=workspace.cfg.host_pattern,
                workflow=workspace.cfg.workflow.__class__.__qualname__,
                worker_command="check" if _check_mode else "run",
                worker_hostname=socket.gethostname(),
                worker_username=getpass.getuser(),
            )
        )
    except ConnectionRefusedError:
        raise BoardwalkException(f"Could not connect to server {boardwalkd_url}")

    # Lock the Workspace at the server
    try:
        boardwalkd_client.mutex()
    except WorkspaceHasMutex:
        raise BoardwalkException(
            f"A workspace with the name {workspace.name} has already locked on {boardwalkd_url}"
        )
    except ConnectionRefusedError:
        raise BoardwalkException(f"Could not connect to server {boardwalkd_url}")

    # Create unmutex callback
    def unmutex_boardwalkd_workspace():
        """Wraps unmutex to prevent crashing if we can't connect"""
        if not boardwalkd_client:
            raise BoardwalkException(
                "unmutex_boardwalkd_workspace called but no boardwalkd_client exists"
            )
        try:
            boardwalkd_client.unmutex()
        except ConnectionRefusedError:
            boardwalk_logger.error(
                f"Could not connect to {boardwalkd_url}. Cannot unmutex Workspace"
            )
        except HTTPClientError as e:
            boardwalk_logger.error(
                f"Received error {e} from {boardwalkd_url}. Cannot unmutex Workspace"
            )

    ctx.call_on_close(unmutex_boardwalkd_workspace)

    # Send heartbeats in background
    heartbeat_coroutine = boardwalkd_client.heartbeat_keepalive_connect()
    ctx.call_on_close(heartbeat_coroutine.cancel)


def update_host_facts_in_local_state(host: Host, workspace: Workspace):
    """Updates fetches latest host facts for a host and saves to the workspace state"""
    boardwalk_logger.info(f"{host.name}: Updating Ansible facts in local state")
    if boardwalkd_client:
        boardwalkd_client.queue_event(
            WorkspaceEvent(
                severity="info",
                message=f"{host.name}: Updating Ansible facts in local state",
            ),
        )
    workspace.state.hosts[host.name].ansible_facts = host.gather_facts()
    workspace.flush()


def directly_confirm_host_preconditions(
    host: Host, inventory_vars: InventoryHostVars, workspace: Workspace
) -> bool:
    """Connects directly to the host and confirms that the workflow job preconditions
    are actually met. Raises an exception if any are unmet. If a workflow was run but
    never completed, preconditions are ignored. Also posts events to the central server"""
    if boardwalkd_client:
        boardwalkd_client.queue_event(
            WorkspaceEvent(
                severity="info",
                message=f"{host.name}:  Checking Job preconditions on host",
            ),
        )
    update_host_facts_in_local_state(host, workspace)

    if workspace.cfg.workflow.cfg.always_retry_failed_hosts:
        # If the workflow was started but never finished, ignore preconditions
        try:
            boardwalk_state = RemoteStateModel.parse_obj(
                host.ansible_facts["ansible_local"]["boardwalk_state"]
            )
            if (
                boardwalk_state.workspaces[workspace.name].workflow.started
                and not boardwalk_state.workspaces[workspace.name].workflow.succeeded
            ):
                boardwalk_logger.warn(
                    (
                        f"{host.name}: Host started workflow but never completed."
                        " Job preconditions are ignored for this host"
                    )
                )
                return True
        except KeyError:
            pass

    all_job_preconditions_met = True
    workflow = workspace.cfg.workflow
    for job in chain(workflow.i_jobs, workflow.i_exit_jobs):
        if not job.preconditions(
            facts=host.ansible_facts, inventory_vars=inventory_vars
        ):
            all_job_preconditions_met = False
            boardwalk_logger.warn(f"Job {job.name} preconditions unmet on host")
    if boardwalkd_client and not all_job_preconditions_met:
        boardwalkd_client.queue_event(
            WorkspaceEvent(
                severity="info",
                message=f"{host.name}:  Host didn't meet job preconditions",
            ),
        )

    if not all_job_preconditions_met:
        raise HostPreConditionsUnmet

    return True


def execute_workflow_jobs(host: Host, workspace: Workspace, job_kind: str):
    """
    Executes workflow jobs. Different kinds of job types are specified
    """
    workflow = workspace.cfg.workflow
    if job_kind == "main":
        jobs = workflow.i_jobs
    elif job_kind == "exit":
        jobs = workflow.i_exit_jobs
    else:
        raise Exception
    if len(jobs) == 0:
        return
    boardwalk_logger.info(f"{host.name}: Running workflow {job_kind} jobs")
    if boardwalkd_client:
        boardwalkd_client.queue_event(
            WorkspaceEvent(
                severity="info",
                message=f"{host.name}: Running workflow {job_kind} jobs",
            ),
        )
    workflow = workspace.cfg.workflow
    for job in jobs:
        if boardwalkd_client:
            boardwalkd_client.queue_event(
                WorkspaceEvent(
                    severity="info",
                    message=f"{host.name}: Running {job_kind} job {job.name}",
                ),
            )
        # Get tasks (which may also run user-supplied python code locally)
        tasks = job.tasks()
        if len(tasks) > 0:
            host.ansible_run(
                become_password=become_password,
                become=True,
                check=_check_mode,
                gather_facts=False,
                invocation_msg=f"{job_kind}_Job_{job.name}",
                quiet=False,
                tasks=tasks,
            )


def execute_host_workflow(host: Host, workspace: Workspace):
    """Handles executing all jobs defined in a workflow against a host"""
    unreachable_exception = None

    boardwalk_logger.info(f"{host.name}: Updating remote state")
    if boardwalkd_client:
        boardwalkd_client.queue_event(
            WorkspaceEvent(
                severity="info",
                message=f"{host.name}: Updating remote state",
            ),
        )
    remote_state = host.get_remote_state()
    try:
        remote_state.workspaces[workspace.name].workflow.started = True
    except KeyError:
        remote_state.workspaces[workspace.name] = RemoteStateWorkspace(
            workflow=RemoteStateWorkflow(started=True)
        )
    host.set_remote_state(remote_state, become_password, _check_mode)

    if boardwalkd_client:
        boardwalkd_client.queue_event(
            WorkspaceEvent(
                severity="info",
                message=f"{host.name}: Starting workflow",
            ),
            broadcast=boardwalkd_send_broadcasts,
        )
    try:
        execute_workflow_jobs(host, workspace, job_kind="main")
    except AnsibleRunnerUnreachableHost as e:
        unreachable_exception = e
    finally:
        # If the host was unreachable there's no point in trying to recover here
        if unreachable_exception:
            raise unreachable_exception
        execute_workflow_jobs(host, workspace, job_kind="exit")

    boardwalk_logger.info(f"{host.name}: Updating remote state")
    if boardwalkd_client:
        boardwalkd_client.queue_event(
            WorkspaceEvent(
                severity="info",
                message=f"{host.name}: Updating remote state",
            ),
        )
    remote_state = host.get_remote_state()
    try:
        remote_state.workspaces[workspace.name].workflow.succeeded = True
    except KeyError:
        remote_state.workspaces[workspace.name] = RemoteStateWorkspace(
            workflow=RemoteStateWorkflow(started=True, succeeded=True)
        )
    host.set_remote_state(remote_state, become_password, _check_mode)

    if boardwalkd_client:
        boardwalkd_client.queue_event(
            WorkspaceEvent(
                severity="success",
                message=f"{host.name}: Host completed successfully; wrapping up",
            ),
            broadcast=boardwalkd_send_broadcasts,
        )
    update_host_facts_in_local_state(host, workspace)


class NoHostsMatched(Exception):
    """No hosts matched regex"""


class HostPreConditionsUnmet(Exception):
    """The host doesn't meet job preconditions"""
