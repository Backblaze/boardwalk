from __future__ import annotations

import os
from typing import TYPE_CHECKING

from pylib.regression_bz_svreng_609 import *  # noqa: F403
from pylib.remote_state_set_unsuccessful_during_active_workflow import *  # noqa: F403

from boardwalk import PlaybookJob, TaskJob, Workflow, Workspace, WorkspaceConfig, path

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


class UITestVeryVeryLongWorkSpaceNameWorkspace(Workspace):
    def config(self):
        return WorkspaceConfig(
            host_pattern="localhost:!foo:!bar:!baz:!fizz:!buzz:!my-very-long-host-name",
            workflow=UITestVerVeryLongWorkflowNameWorkflow(),
        )


class MalformedYAMLWorkspace(Workspace):
    def config(self):
        return WorkspaceConfig(
            host_pattern="localhost",
            workflow=MalformedYAMLWorkflow(),
        )


class ShouldSucceedPlaybookExecutionTestWorkspace(Workspace):
    def config(self):
        return WorkspaceConfig(
            host_pattern="localhost",
            workflow=ShouldSucceedPlaybookExecutionTestWorkflow(),
        )


class ShouldFailPlaybookExecutionTestWorkspace(Workspace):
    def config(self):
        return WorkspaceConfig(
            host_pattern="localhost",
            workflow=ShouldFailPlaybookExecutionTestWorkflow(),
        )


class ShouldSucceedMixedJobTypesWorkspace(Workspace):
    def config(self):
        return WorkspaceConfig(
            host_pattern="localhost",
            workflow=ShouldSucceedMixedJobTypesWorkflow(),
        )


class UITestVerVeryLongWorkflowNameWorkflow(Workflow):
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


class ShouldSucceedPlaybookExecutionTestWorkflow(Workflow):
    def jobs(self):
        return ShouldSucceedPlaybookExecutionTestJob()

    def exit_jobs(self):
        return TestJob()


class ShouldFailPlaybookExecutionTestWorkflow(Workflow):
    def jobs(self):
        return ShouldFailPlaybookExecutionTestJob()

    def exit_jobs(self):
        return TestJob()


class ShouldSucceedMixedJobTypesWorkflow(Workflow):
    def jobs(self):
        return [
            TestJob(),
            ShouldSucceedPlaybookExecutionTestJob(),
        ]

    def exit_jobs(self):
        return TestJob()


class TestJob(TaskJob):
    def tasks(self) -> AnsibleTasksType:
        return [{"ansible.builtin.debug": {"msg": "Hello, Boardwalk!"}}]


class FailTestJob(TaskJob):
    def tasks(self) -> AnsibleTasksType:
        return [{"ansible.builtin.fail": {"msg": "Task failed successfully."}}]


class MalformedYAMLJob(TaskJob):
    """
    Tests a playbook that has malformed YAML
    """

    def tasks(self) -> AnsibleTasksType:
        return [{"ansible.builtin.import_tasks": path("playbooks/malformed_playbook.yml")}]


class ShouldSucceedPlaybookExecutionTestJob(PlaybookJob):
    """
    Tests importing and running full playbooks against a specified host.
    """

    def playbooks(self) -> AnsibleTasksType:
        return [
            {"ansible.builtin.import_playbook": path("playbooks/playbook-job-test-should-succeed.yml")},
            {"ansible.builtin.import_playbook": path("playbooks/playbook-job-test-should-be-skipped.yml")},
        ]


class ShouldFailPlaybookExecutionTestJob(PlaybookJob):
    """
    Tests importing and running full playbooks against a specified host.
    """

    def playbooks(self) -> AnsibleTasksType:
        return [
            {"ansible.builtin.import_playbook": path("playbooks/playbook-job-test-should-succeed.yml")},
            {"ansible.builtin.import_playbook": path("playbooks/playbook-job-test-should-be-skipped.yml")},
            {"ansible.builtin.import_playbook": path("playbooks/playbook-job-test-should-fail.yml")},
        ]
