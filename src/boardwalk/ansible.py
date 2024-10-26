"""
This file has utilities for working with Ansible
"""

from __future__ import annotations

import json
import sys
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

import ansible_runner
from loguru import logger

import boardwalk
from boardwalk.app_exceptions import BoardwalkException

if TYPE_CHECKING:
    from typing import Any, TypedDict

    from ansible_runner import Runner

    from boardwalk.manifest import Workspace

    class InventoryData(TypedDict):
        _meta: InventoryMetaData

    class InventoryMetaData(TypedDict):
        hostvars: HostVarsType

    AnsibleFacts = dict[str, Any]
    InventoryHostVars = dict[str, Any]
    HostVarsType = dict[str, InventoryHostVars]
    AnsibleTaskType = dict[str, str | int | bool | list[str] | "AnsibleTaskType"]
    AnsibleTasksType = list[AnsibleTaskType]

    class RunnerKwargs(TypedDict, total=False):
        cancel_callback: partial[bool]
        cmdline: str | None
        envvars: RunnerKwargsEnvvars
        fact_cache_type: str
        limit: str | None
        passwords: dict[str, str | None]
        project_dir: str
        quiet: bool
        suppress_env_files: bool
        playbook: RunnerPlaybook | AnsibleTasksType
        verbosity: int
        extravars: dict[str, Any] | None

    class RunnerKwargsEnvvars(TypedDict, total=False):
        ANSIBLE_BECOME_ASK_PASS: str
        ANSIBLE_CACHE_PLUGIN_CONNECTION: str
        ANSIBLE_CACHE_PLUGIN: str
        ANSIBLE_NOCOLOR: str
        ANSIBLE_TASK_TIMEOUT: str

    class RunnerPlaybook(TypedDict, total=False):
        become: bool
        gather_facts: bool
        hosts: str
        tasks: AnsibleTasksType
        vars: dict[str, str | bool]


def ansible_runner_cancel_callback(ws: Workspace):
    """
    ansible_runner needs a callback to tell it to stop execution. It returns
    True to stop execution. We check for the workspace.mutex because that file
    is always supposed to be torn down on exit
    """
    if ws.path.joinpath("workspace.mutex").exists():
        return False
    else:
        return True


def ansible_runner_errors_to_output(runner: Runner, include_msg: bool = True) -> str:
    """Collects error messages from a Runner into a multiline string"""
    output: list[str] = []
    for event in runner.events:
        if (
            event["event"] == "runner_on_failed"
            or event["event"] == "runner_item_on_failed"
            or event["event"] == "runner_on_async_failed"
            or event["event"] == "runner_on_unreachable"
        ) and not ("ignore_errors" in event["event_data"] and event["event_data"]["ignore_errors"]):
            msg: list[str] = [
                event["event"],
                event["event_data"]["task"],
                event["event_data"]["task_action"],
                event["event_data"]["host"],
            ]
            if include_msg and not (
                "_ansible_no_log" in event["event_data"]["res"] and event["event_data"]["res"]["_ansible_no_log"]
            ):
                try:
                    msg.append(event["event_data"]["res"]["msg"])
                except KeyError:
                    logger.warning("Event error did not contain msg")
                try:
                    msg.append(event["stdout"])
                except KeyError:
                    logger.warning("Event error did not contain stdout")
            output.append(": ".join(msg))
    return "\n".join(output)


def ansible_runner_run_tasks(
    hosts: str,
    invocation_msg: str,
    job_type: boardwalk.manifest.JobTypes,
    tasks: AnsibleTasksType,
    become: bool = False,
    become_password: str | None = None,
    check: bool = False,
    gather_facts: bool = True,
    limit: str | None = None,
    quiet: bool = True,
    timeout: int | None = None,
    verbosity: int = 0,
    extra_vars: dict = {},
) -> ansible_runner.Runner:
    """
    Wraps ansible_runner.run to run Ansible tasks with some defaults for
    Boardwalk
    """
    workspace = boardwalk.manifest.get_ws()

    runner_kwargs: RunnerKwargs = {
        "cancel_callback": partial(ansible_runner_cancel_callback, workspace),
        "envvars": {
            "ANSIBLE_BECOME_ASK_PASS": "False" if become_password is None else "True",
            "ANSIBLE_CACHE_PLUGIN_CONNECTION": str(workspace.path.joinpath("fact_cache")),
            "ANSIBLE_CACHE_PLUGIN": "community.general.pickle",
            "ANSIBLE_NOCOLOR": "True",
        },
        "fact_cache_type": "community.general.pickle",
        "passwords": {r"^BECOME password:\s*$": become_password},
        "project_dir": str(Path.cwd()),
        "quiet": quiet,
        "suppress_env_files": True,
        "verbosity": verbosity,
    }
    if check:
        runner_kwargs["cmdline"] = "--check"
    if limit:
        runner_kwargs["limit"] = limit
    if timeout:
        runner_kwargs["envvars"]["ANSIBLE_TASK_TIMEOUT"] = str(timeout)

    logger.trace(f"Constructing runner_kwargs for job type {job_type.name}")
    if job_type == boardwalk.manifest.JobTypes.TASK:
        runner_kwargs["playbook"] = {
            "hosts": hosts,
            "gather_facts": gather_facts,
            "become": become,
            "tasks": tasks,
            "vars": {"boardwalk_operation": True},
        }
    if job_type == boardwalk.manifest.JobTypes.PLAYBOOK:
        # Executing a (list of) playbook(s) requires some different settings
        runner_kwargs["limit"] = hosts
        runner_kwargs["extravars"] = {"boardwalk_operation": True} | extra_vars
        runner_kwargs["playbook"] = tasks

    output_msg_prefix = f"{hosts}: ansible_runner invocation"
    if limit:
        output_msg_prefix = f"{hosts}(limit: {limit}): ansible_runner invocation"
    output_msg = f"{output_msg_prefix}: {invocation_msg}"
    logger.info(output_msg)
    runner: Runner = ansible_runner.run(**runner_kwargs)  # type: ignore
    runner_errors = ansible_runner_errors_to_output(runner)
    fail_msg = f"Error:\n{output_msg}\n{runner_errors}"
    if runner.rc != 0:
        if runner.rc == 1:
            raise AnsibleRunError(fail_msg, output_msg, runner)
        elif runner.rc == 2:
            raise AnsibleRunnerFailedHost(fail_msg, output_msg, runner)
        elif runner.rc == 4:
            raise AnsibleRunnerUnreachableHost(fail_msg, output_msg, runner)
        # Catch any other errors here
        else:
            raise AnsibleRunnerGeneralError(fail_msg, output_msg, runner)
    else:
        return runner


def ansible_inventory() -> InventoryData:
    """Uses ansible-inventory to fetch the inventory and returns it as a dict"""
    logger.info("Processing ansible-inventory")
    """
    Note that for the moment we have --export set here. --export won't expand Jinja
    expressions and this is done for performance reasons. It's entirely possible
    that there will be cases where a user does want Jinja expressions to be fully
    processed
    """
    out, err, rc = ansible_runner.run_command(
        envvars={"ANSIBLE_VERBOSITY": 0},
        executable_cmd="ansible-inventory",
        cmdline_args=["--list", "--export"],
        input_fd=sys.stdin,
        project_dir=str(Path.cwd()),
        quiet=True,
        suppress_env_files=True,
    )
    if rc != 0:
        BoardwalkException(f"Failed to render inventory. {err}")

    return json.loads(out)


class AnsibleRunnerBaseException(Exception):
    """
    Base class for throwing ansible_runner exceptions. Allows the Runner to be
    passed in
    """

    def __init__(self, message: str, runner_msg: str, runner: Runner):
        super().__init__(message)
        self.runner_msg = runner_msg
        self.runner = runner


class AnsibleRunnerGeneralError(AnsibleRunnerBaseException):
    """There was a non-specific ansible_runner failure"""


class AnsibleRunError(AnsibleRunnerBaseException):
    """There was an error running a playbook"""


class AnsibleRunnerUnreachableHost(AnsibleRunnerBaseException):
    """A host was unreachable to ansible_runner"""


class AnsibleRunnerFailedHost(AnsibleRunnerBaseException):
    """A host failed while running ansible_runner"""
