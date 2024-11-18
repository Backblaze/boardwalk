"""The remote state file should have a workspace's workflow set as succeeded=false during a workspace execution.

Scenario:
- A workflow -- call it DebianDistUpgradeWorkflow -- provides an option to a
Job, such that it targets a specific version of Debian for system upgrades. For
instance, Debian 10 to 11. During workflow execution, the state file on the
targeted system(s) is updated -- at /etc/ansible/facts.d/boardwalk_state.fact --
which permits resuming the workflow on a host which has not yet successfully
completed the workflow, even if the host no longer meets the defined
preconditions.
  - This is useful, for instance, when upgrading a host from one major OS
    version to the next. During the process, the underlying Ansible facts would
    -- eventually -- detect that the OS is now upgraded, resulting in the host
    no longer meeting defined preconditions.
- The workspace in which this workflow was used -- say,
  UpgradeTestingHostsWorkspace -- completes successfully. Thus, the `succeeded`
  value for the workspace/flow is updated to 'true'.
- The host -- at some point, such as when re-using the same Workspace/Workflow
  for Debian 11 to 12 upgrades (with associated additional version specific
  tasks, of course) -- now meets preconditions once again, but fails at some
  point. Before this test and corresponding code change, the succeeded value
  would still be 'true', resulting in the inability to fully complete the
  workflow against the targeted host; at least, that is, without manually
  intervening on the host to edit the remote state-file to set succeeded as
  false. This is due to the fact that the 'success' value was only set to 'true'
  at the successful completion of the workflow, and not set to 'false' at the
  initiation of a workflow.

Stated differently, before this point, the statefile would look like the
following _if_ the same workspace had completed on the host successfully; in the
event the host now again meets preconditions, and failed, the host would not be
able to re-enter the Workspace (without manually altering the on-host state)
```
# Bad =(
{"workspaces":{"ShouldSucceedTestWorkspace":{"workflow":{"started":true,"succeeded":true}}}}
```

However, the state file should be equivalent to the following when Boardwalk
decides it wants to work on a host; in the event it does, this would permit the
workflow to be resumed without needing to manually intervene in the event of a
failed run.
```
# Good! =)
{"workspaces":{"ShouldSucceedTestWorkspace":{"workflow":{"started":true,"succeeded":false}}}}
```

Test run example prior to modifying `boardwalk` to account for this error.
```
2024-11-18 13:59:58.619 | ERROR    | boardwalk.cli_run:run_failure_mode_handler:358 - Error:
127.0.0.1: ansible_runner invocation: main_TASK_Job_RemoteStateShouldHaveWorkflowSucceededValueSetAsFalseDuringExecutionTaskJob
runner_on_failed: ensure-remote-workflow-success-state-false-during-run | Assert that the running workspace's workflow has not succeeded:
    ansible.builtin.assert: 127.0.0.1: The workspace RemoteStateShouldHaveWorkflowSucceededValueSetAsFalseDuringExecutionWorkspace does not
    have its remote state set as `started == True` and `succeeded == False`; a workflow that is currently executing cannot, by definition,
    have its workflow as both started and succeeded. The remote state is currently set to `started == True` and `succeeded == True`.
: fatal: [127.0.0.1]: FAILED! => changed=false
  assertion: boardwalk_state["workspaces"][test_workspace_name]["workflow"]["succeeded"] == False
  evaluated_to: false
  msg: |-
    The workspace RemoteStateShouldHaveWorkflowSucceededValueSetAsFalseDuringExecutionWorkspace does not have its remote state set as
    `started == True` and `succeeded == False`; a workflow that is currently executing cannot, by definition, have its workflow as both
    started and succeeded. The remote state is currently set to `started == True` and `succeeded == True`.
127.0.0.1: Job encountered error; Workspace will catch
```
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from boardwalk import AnsibleTasksType

from boardwalk import TaskJob, Workflow, Workspace, WorkspaceConfig, path

__all__ = [
    "RemoteStateShouldHaveWorkflowSucceededValueSetAsFalseDuringExecutionWorkspace",
]


class RemoteStateShouldHaveWorkflowSucceededValueSetAsFalseDuringExecutionWorkspace(Workspace):
    def config(self):
        return WorkspaceConfig(
            default_sort_order="ascending",
            host_pattern="localhost",
            workflow=RemoteStateShouldHaveWorkflowSucceededValueSetAsFalseDuringExecutionWorkflow(),
        )


class RemoteStateShouldHaveWorkflowSucceededValueSetAsFalseDuringExecutionWorkflow(Workflow):
    def jobs(self):
        return (
            RemoteStateShouldHaveWorkflowSucceededValueSetAsFalseDuringExecutionTaskJob(
                options={
                    "test_workspace_name": "RemoteStateShouldHaveWorkflowSucceededValueSetAsFalseDuringExecutionWorkspace"
                }
            ),
        )


class RemoteStateShouldHaveWorkflowSucceededValueSetAsFalseDuringExecutionTaskJob(TaskJob):
    def required_options(self) -> str:
        return "test_workspace_name"

    def tasks(self) -> AnsibleTasksType:
        return [
            {"set_fact": {"test_workspace_name": self.options["test_workspace_name"]}},
            {"ansible.builtin.import_tasks": path("tasks/ensure-remote-workflow-success-state-false-during-run.yml")},
        ]
