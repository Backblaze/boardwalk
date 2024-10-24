"""
init CLI subcommand
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

import click
from loguru import logger

from boardwalk.ansible import (
    AnsibleRunError,
    AnsibleRunnerFailedHost,
    AnsibleRunnerGeneralError,
    AnsibleRunnerUnreachableHost,
    ansible_runner_run_tasks,
)
from boardwalk.app_exceptions import BoardwalkException
from boardwalk.host import Host
from boardwalk.manifest import JobTypes, NoActiveWorkspace, Workspace, get_ws

if TYPE_CHECKING:
    from ansible_runner import RunnerEvent

    from boardwalk.ansible import AnsibleTasksType

    class runnerKwargs(TypedDict, total=False):
        gather_facts: bool
        hosts: str
        hosts: str
        invocation_msg: str
        limit: str
        tasks: AnsibleTasksType
        timeout: int


@click.command(short_help="Inits local workspace state by getting host facts")
@click.option(
    "--limit",
    "-l",
    help="An Ansible pattern to limit hosts by. Defaults to no limit",
    default="all",
)
@click.option(
    "--retry/--no-retry",
    "-r/-nr",
    default=False,
    help="Retry getting state for hosts that were unreachable/failed on the last attempt",
    show_default=True,
)
@click.pass_context
def init(ctx: click.Context, limit: str, retry: bool):
    """
    Inits the workspace state with host data. Gathers Ansible facts for hosts
    matching the workspaces host pattern. OK to run multiple times; hosts are
    only added or updated, never removed by this operation. Use
    `boardwalk workspace reset` to clear existing state if needed
    """
    if retry and limit not in ["all", ""]:
        # We don't allow limit and retry to be specified together at the moment
        raise BoardwalkException("--limit and --retry cannot be supplied together")

    try:
        ws = get_ws()
    except NoActiveWorkspace as e:
        raise BoardwalkException(e.message)
    logger.info(f"Using workspace: {ws.name}")

    ws.assert_host_pattern_unchanged()

    ws.mutex()
    ctx.call_on_close(ws.unmutex)

    retry_file_path = ws.path.joinpath("init.retry")

    # Set-up Ansible args
    runner_kwargs: runnerKwargs = {
        "gather_facts": False,
        "hosts": ws.cfg.host_pattern,
        "invocation_msg": "Gathering facts",
        "limit": limit,
        "tasks": [{"name": "setup", "ansible.builtin.setup": {"gather_timeout": 30}}],
        "timeout": 300,
    }
    if retry:
        if not retry_file_path.exists():
            raise BoardwalkException("No retry file exists")
        runner_kwargs["limit"] = f"@{str(retry_file_path)}"

    # Save the host pattern we are initializing with. If the pattern changes after
    # this point, other operations will need the state reset and init to be re-done
    ws.state.host_pattern = ws.cfg.host_pattern

    # Run Ansible
    hosts_were_unreachable = False
    try:
        runner = ansible_runner_run_tasks(**runner_kwargs, job_type=JobTypes.TASK)
    except (
        AnsibleRunnerFailedHost,
        AnsibleRunnerGeneralError,
        AnsibleRunnerUnreachableHost,
    ) as e:
        # Unreachable and failed hosts are not a hard failure
        # We note to the user later on if hosts were unreachable
        hosts_were_unreachable = True
        runner = e.runner
    except AnsibleRunError as e:
        # If we encounter this error type, there is likely some local error, so
        # we try to print out some debug info and bail
        for event in e.runner.events:
            try:
                logger.error(event["stdout"])
            except KeyError:
                pass
        raise BoardwalkException("Failed to start fact gathering")

    # Clear the retry file after we use it to start fresh before we build a new one
    retry_file_path.unlink(missing_ok=True)

    # Process Ansible output
    # Collects facts into state
    for event in runner.events:
        add_gathered_facts_to_state(event, ws)
        handle_failed_init_hosts(event, retry_file_path)
    ws.flush()

    # Write out stats
    for event in runner.events:
        if event["event"] == "playbook_on_stats":
            click.echo(event["stdout"])

    # Note if any hosts were unreachable
    if hosts_were_unreachable:
        logger.warning("Some hosts were unreachable. Consider running again with --retry")

    # If we didn't find any hosts, raise an exception
    if len(ws.state.hosts) == 0:
        raise BoardwalkException("No hosts gathered")


def add_gathered_facts_to_state(event: RunnerEvent, ws: Workspace):
    """
    Adds or updates gathered host facts in the workspace state
    """
    if event["event"] == "runner_on_ok" and event["event_data"]["task"] == "setup":
        # If the host is already in the statefile, just update record
        if event["event_data"]["host"] in ws.state.hosts:
            ws.state.hosts[event["event_data"]["host"]].ansible_facts = event["event_data"]["res"]["ansible_facts"]
        # Otherwise, add the host to the state as a new host
        else:
            ws.state.hosts[event["event_data"]["host"]] = Host(
                ansible_facts=event["event_data"]["res"]["ansible_facts"],
                name=event["event_data"]["host"],
            )


def handle_failed_init_hosts(event: RunnerEvent, retry_file_path: Path):
    """Processes runner events to find failed hosts during init. Saves any failed
    or unreachable hosts to a retry file and writes warnings and errors to stdout"""
    # Save any unreachable/failed hosts to the retry file
    if event["event"] == "runner_on_unreachable" or event["event"] == "runner_on_failed":
        logger.warning(event["stdout"])
        with open(retry_file_path, "a") as file:
            file.write(f"{event['event_data']['host']}\n")
    # If no hosts matched or there are warnings, write them out
    if event["event"] == "warning" or event["event"] == "playbook_on_no_hosts_matched":
        logger.warning(event["stdout"])
