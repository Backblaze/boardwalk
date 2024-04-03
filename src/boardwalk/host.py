"""
This file contains everything about what host data is stored and what can be
done to hosts
"""

from __future__ import annotations

import getpass
import socket
from base64 import b64decode
from datetime import datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Extra

import boardwalk
from boardwalk.ansible import ansible_runner_run_tasks
from boardwalk.app_exceptions import BoardwalkException

if TYPE_CHECKING:
    from ansible_runner import Runner

    from boardwalk.ansible import AnsibleTasksType


class Host(BaseModel, extra=Extra.forbid):
    """Data and methods for managing an individual host"""

    ansible_facts: dict[str, Any]
    name: str
    meta: dict[str, str | int | bool] = {}
    remote_mutex_path: str = "/opt/boardwalk.mutex"
    remote_alert_msg: str = "ALERT: Boardwalk is running a workflow against this host. Services may be interrupted"
    remote_alert_string_formatted: str = f"$(tput -T xterm bold)$(tput -T xterm setaf 1)'{remote_alert_msg}'$(tput -T xterm sgr0)"
    remote_alert_motd: str = f"#!/bin/sh\necho {remote_alert_string_formatted}"
    remote_alert_motd_path: str = "/etc/update-motd.d/99-boardwalk-alert"
    remote_alert_wall_cmd: str = f"wall {remote_alert_string_formatted}"

    def ansible_run(
        self,
        invocation_msg: str,
        tasks: AnsibleTasksType,
        become: bool = False,
        become_password: str | None = None,
        check: bool = False,
        gather_facts: bool = True,
        quiet: bool = True,
    ) -> Runner:
        """
        Wraps ansible_runner_run_tasks for performing Ansible tasks against this host
        """
        return ansible_runner_run_tasks(
            hosts=self.name,
            invocation_msg=invocation_msg,
            tasks=tasks,
            become=become,
            become_password=become_password,
            check=check,
            gather_facts=gather_facts,
            quiet=quiet,
        )

    def is_locked(self) -> str | bool:
        """
        Checks if a remote host is locked
        Returns string with lockfile content if so, False otherwise
        """
        tasks: AnsibleTasksType = [
            {
                "name": "remote_mutex_check",
                "ansible.builtin.stat": {"path": self.remote_mutex_path},
                "register": "lockfile",
            },
            {
                "name": "slurp_mutex_content",
                "ansible.builtin.slurp": {"src": self.remote_mutex_path},
                "when": "lockfile.stat.exists",
            },
        ]

        runner = self.ansible_run(
            invocation_msg="check_remote_host_lock",
            gather_facts=False,
            tasks=tasks,
        )

        lockfile_stat_exists = False
        slurp_mutex_content = ""
        for event in runner.events:
            if event["event"] == "runner_on_ok":
                if event["event_data"]["task"] == "remote_mutex_check":
                    lockfile_stat_exists = event["event_data"]["res"]["stat"]["exists"]
                if event["event_data"]["task"] == "slurp_mutex_content":
                    slurp_mutex_content = event["event_data"]["res"]["content"]
        if lockfile_stat_exists:
            return b64decode(slurp_mutex_content).decode("utf-8").rstrip()
        return False

    def lock(
        self,
        become_password: str | None = None,
        check: bool = False,
        stomp_existing_locks: bool = False,
    ):
        """
        Sets a remote lock and writes an alert for any local users
        If a lock is already set, an error is raised
        """

        if not stomp_existing_locks and (res := self.is_locked()):
            # Check if there is already a lock on the host
            raise RemoteHostLocked(f"{self.name}: Host is locked by {res}")
        tasks: AnsibleTasksType = [
            {"name": "get_ansible_system", "setup": {"filter": ["ansible_system"]}},
            {
                "name": "set_linux_facts",
                "ansible.builtin.set_fact": {"admin_group": "root"},
                "when": "ansible_system == 'Linux'",
            },
            {
                "name": "set_darwin_facts",
                "ansible.builtin.set_fact": {"admin_group": "wheel"},
                "when": "ansible_system == 'Darwin'",
            },
            {
                "name": "create_remote_lock",
                "ansible.builtin.copy": {
                    "content": f"{getpass.getuser()}@{socket.gethostname()} at {datetime.utcnow()}",
                    "dest": str(self.remote_mutex_path),
                    "mode": "0644",
                    "owner": "root",
                    "group": "{{ admin_group }}",
                },
            },
            {
                "name": "create_motd_banner",
                "ansible.builtin.copy": {
                    "content": self.remote_alert_motd,
                    "dest": self.remote_alert_motd_path,
                    "owner": "root",
                    "group": "{{ admin_group }}",
                    "mode": "0755",
                },
                "when": "ansible_system == 'Linux'",
            },
            {
                "name": "write_wall_msg",
                "ansible.builtin.shell": {"cmd": self.remote_alert_wall_cmd},
                "when": "ansible_system == 'Linux'",
            },
        ]
        self.ansible_run(
            become=True,
            become_password=become_password,
            check=check,
            gather_facts=False,
            invocation_msg="lock_remote_host",
            tasks=tasks,
        )

    def release(self, become_password: str | None = None, check: bool = False) -> None:
        """Undoes the lock method"""
        tasks: AnsibleTasksType = [
            {
                "name": "release_remote_lock",
                "ansible.builtin.file": {
                    "path": self.remote_mutex_path,
                    "state": "absent",
                },
            },
            {
                "name": "delete_motd_banner",
                "ansible.builtin.file": {
                    "path": self.remote_alert_motd_path,
                    "state": "absent",
                },
            },
        ]
        self.ansible_run(
            become=True,
            become_password=become_password,
            check=check,
            gather_facts=False,
            invocation_msg="release_remote_host",
            tasks=tasks,
        )

    def gather_facts(self) -> dict[str, Any]:
        """Returns the output of Ansible's setup module"""
        tasks: AnsibleTasksType = [
            {"name": "setup", "ansible.builtin.setup": {"gather_timeout": 30}}
        ]
        runner = self.ansible_run(
            invocation_msg="gather_facts",
            gather_facts=False,
            tasks=tasks,
        )
        facts: dict[str, Any] = {"ansible_local": {}}
        for event in runner.events:
            if (
                event["event"] == "runner_on_ok"
                and event["event_data"]["task"] == "setup"
            ):
                facts = event["event_data"]["res"]["ansible_facts"]
        if len(facts) > 0:
            return facts
        else:
            raise BoardwalkException("gather_facts returned nothing")

    def get_remote_state(self) -> boardwalk.state.RemoteStateModel:
        """Gets boardwalk's remote state fact as an object"""

        # Get existing ansible_local facts, if any
        tasks: AnsibleTasksType = [
            {"name": "setup", "ansible.builtin.setup": {"filter": ["ansible_local"]}}
        ]
        runner = self.ansible_run(
            invocation_msg="get_remote_state",
            gather_facts=False,
            tasks=tasks,
        )

        # Get existing boardwalk_state fact, if any
        for event in runner.events:
            if (
                event["event"] == "runner_on_ok"
                and event["event_data"]["task"] == "setup"
            ):
                try:
                    return boardwalk.RemoteStateModel.parse_obj(
                        event["event_data"]["res"]["ansible_facts"]["ansible_local"][
                            "boardwalk_state"
                        ]
                    )
                except KeyError:
                    pass

        return boardwalk.RemoteStateModel()

    def set_remote_state(
        self,
        remote_state_obj: boardwalk.state.RemoteStateModel,
        become_password: str | None = None,
        check: bool = False,
    ):
        """Sets the remote state fact from an object in the remote and local state"""
        workspace = boardwalk.manifest.get_ws()
        tasks: AnsibleTasksType = [
            {"name": "get_ansible_system", "setup": {"filter": ["ansible_system"]}},
            {
                "name": "set_linux_facts",
                "ansible.builtin.set_fact": {"admin_group": "root"},
                "when": "ansible_system == 'Linux'",
            },
            {
                "name": "set_darwin_facts",
                "ansible.builtin.set_fact": {"admin_group": "wheel"},
                "when": "ansible_system == 'Darwin'",
            },
            {
                "name": "ensure_ansible_local_facts_dir",
                "ansible.builtin.file": {
                    "state": "directory",
                    "path": "/etc/ansible/facts.d",
                },
            },
            {
                "name": "update_remote_state",
                "ansible.builtin.copy": {
                    "content": remote_state_obj.json(),
                    "dest": "/etc/ansible/facts.d/boardwalk_state.fact",
                    "mode": "0644",
                    "owner": "root",
                    "group": "{{ admin_group }}",
                },
            },
        ]
        self.ansible_run(
            become=True,
            become_password=become_password,
            check=check,
            gather_facts=False,
            invocation_msg="set_remote_state",
            tasks=tasks,
        )
        if not check:
            self.ansible_facts["ansible_local"]["boardwalk_state"] = (
                remote_state_obj.dict()
            )
            workspace.flush()


class RemoteHostLocked(BoardwalkException):
    """The remote host is locked by another job"""
