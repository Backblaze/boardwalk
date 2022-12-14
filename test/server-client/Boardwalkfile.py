from __future__ import annotations

import os
from typing import TYPE_CHECKING

from boardwalk import Job, path, Workflow, Workspace, WorkspaceConfig

if TYPE_CHECKING:
    from boardwalk import AnsibleTasksType

boardwalkd_url = "http://localhost:8888/"

# Ansible checks the envvar first for configuration; so override the location with one
# we control so tests work.
os.environ["ANSIBLE_CONFIG"] = os.path.abspath("ansible.cfg")


class ShouldSucceedTestWorkspace(Workspace):
    def config(self):
        return WorkspaceConfig(
            host_pattern="localhost",
            workflow=TestWorkflow(),
        )


class ShouldFailTestWorkspace(Workspace):
    def config(self):
        return WorkspaceConfig(
            host_pattern="localhost",
            workflow=FailTestWorkflow(),
        )


class UIAbuseTestWorkspace(Workspace):
    def config(self):
        return WorkspaceConfig(
            host_pattern="localhost:!foo:!bar:!baz:!fizz:!buzz:!my-very-long-host-name",
            workflow=UITestVeryLongWorkflowNameWorkflow(),
        )


class MalformedYAMLWorkspace(Workspace):
    def config(self):
        return WorkspaceConfig(
            host_pattern="localhost",
            workflow=MalformedYAMLWorkflow(),
        )


class UITestVeryLongWorkflowNameWorkflow(Workflow):
    def jobs(self):
        return TestJob()


class TestWorkflow(Workflow):
    def jobs(self):
        return TestJob()


class FailTestWorkflow(Workflow):
    def jobs(self):
        return FailTestJob()


class MalformedYAMLWorkflow(Workflow):
    def jobs(self):
        return MalformedYAMLJob()

    def exit_jobs(self):
        return TestJob()


class TestJob(Job):
    def tasks(self) -> AnsibleTasksType:
        return [{"debug": {"msg": "hello test"}}]


class FailTestJob(Job):
    def tasks(self) -> AnsibleTasksType:
        return [{"fail": {"msg": "failed successfully"}}]


class MalformedYAMLJob(Job):
    """
    Tests a playbook that has malformed YAML
    """

    def tasks(self) -> AnsibleTasksType:
        return [{"import_tasks": path("malformed_playbook.yml")}]
