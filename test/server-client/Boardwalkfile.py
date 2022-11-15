from __future__ import annotations

import os
from typing import TYPE_CHECKING

from boardwalk import Job, Workflow, Workspace, WorkspaceConfig

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


class UITestVeryLongWorkflowNameWorkflow(Workflow):
    def jobs(self):
        return TestJob()


class TestWorkflow(Workflow):
    def jobs(self):
        return TestJob()


class FailTestWorkflow(Workflow):
    def jobs(self):
        return FailTestJob()


class TestJob(Job):
    def tasks(self) -> AnsibleTasksType:
        return [{"debug": {"msg": "hello test"}}]


class FailTestJob(Job):
    def tasks(self) -> AnsibleTasksType:
        return [{"fail": {"msg": "failed successfully"}}]
