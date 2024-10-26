"""Regression testing suite for the issue introduced with 0.8.22 with TaskJobs.

Explanation: At the release of Boardwalk 0.8.22, there had not been any test
suites/workspaces which actually made use of the `options` that a Job could
have. Options, in this case, referencing additional variables that can be used,
such as when computing preconditions and are typically also passed through to
the underlying `ansible-playbook` invocation, whether through a `set_fact` task,
or via `--extra_vars/-e` with `ansible-runner` if the PlaybookJob is being used.

The issue here, however, was that we missed having the subclassed TaskJob, (the
deprecated) Job, and the PlaybookJob have the `options` parameter accepted in
the initialization method of the class.

In the case of PlaybookJobs, however, in the interest of trying to keep the code
simple, we have opted to add an `extra_vars` item onto PlaybookJob class
instances, consisting of the `options` passed to the PlaybookJob. These options
-- now extra variables -- are then passed through to the `ansible-runner`
invocation, and will be supplied to `ansible-playbook` as if they were passed to
the `-e`/`--extra-vars` command-line option. This method of providing extra
variables was selected, as it is not possible to include raw tasks in the same
"playbook before/after a full playbook. As such, the following example _does not
work_, and would result in an error propagating up from Ansible which --
effectively -- states that tasks cannot be used in a Play (or similar).

```
class AnExampleWhichDoesNotWork(PlaybookJob):
    def required_options(self) -> tuple[str]:
        return ("boardwalk_playbookjob_test_variable",)

    def tasks(self):
        return [
            {"set_fact": {"boardwalk_playbookjob_test_variable":
            self.options["boardwalk_playbookjob_test_variable"]}},
            {"ansible.builtin.import_playbook":
            path("playbooks/playbook-job-test-echo-variable.yml")},
        ]
```

Example of the error which led to this discovery:
========
asullivan@MBP-NT9RPG2XV7 server-client % boardwalk workspace use
TaskJobsWithOptionsShouldSucceedWorkspace 2024-10-25 13:35:55.995 | INFO     |
boardwalk.cli:cli:77 - Log level is INFO Traceback (most recent call last):
  File "/Users/asullivan/.local/bin/boardwalk", line 10, in <module>
    sys.exit(cli())
             ^^^^^
  File "/Users/asullivan/Library/Application
  Support/pipx/venvs/ansible/lib/python3.12/site-packages/click/core.py", line
  1157, in __call__
    return self.main(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/asullivan/Library/Application
  Support/pipx/venvs/ansible/lib/python3.12/site-packages/click/core.py", line
  1078, in main
    rv = self.invoke(ctx)
         ^^^^^^^^^^^^^^^^
  File "/Users/asullivan/Library/Application
  Support/pipx/venvs/ansible/lib/python3.12/site-packages/click/core.py", line
  1688, in invoke
    return _process_result(sub_ctx.command.invoke(sub_ctx))
                           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/asullivan/Library/Application
  Support/pipx/venvs/ansible/lib/python3.12/site-packages/click/core.py", line
  1688, in invoke
    return _process_result(sub_ctx.command.invoke(sub_ctx))
                           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/asullivan/Library/Application
  Support/pipx/venvs/ansible/lib/python3.12/site-packages/click/core.py", line
  1434, in invoke
    return ctx.invoke(self.callback, **ctx.params)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/asullivan/Library/Application
  Support/pipx/venvs/ansible/lib/python3.12/site-packages/click/core.py", line
  783, in invoke
    return __callback(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/asullivan/Library/Application
  Support/pipx/venvs/ansible/lib/python3.12/site-packages/boardwalk/cli_workspace.py",
  line 48, in workspace_use
    Workspace.use(workspace_name)
  File "/Users/asullivan/Library/Application
  Support/pipx/venvs/ansible/lib/python3.12/site-packages/boardwalk/manifest.py",
  line 440, in use
    ws = get_ws()
         ^^^^^^^^
  File "/Users/asullivan/Library/Application
  Support/pipx/venvs/ansible/lib/python3.12/site-packages/boardwalk/manifest.py",
  line 90, in get_ws
    return Workspace.fetch_subclass(active_workspace_name)()
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/asullivan/Library/Application
  Support/pipx/venvs/ansible/lib/python3.12/site-packages/boardwalk/manifest.py",
  line 337, in __init__
    self.cfg = self.config()
               ^^^^^^^^^^^^^
  File
  "/Users/asullivan/backblaze/github_repos/boardwalk/test/server-client/pylib/regression_svreng_608.py",
  line 18, in config
    workflow=TaskJobsWithOptionsShouldSucceedWorkflow(),
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/asullivan/Library/Application
  Support/pipx/venvs/ansible/lib/python3.12/site-packages/boardwalk/manifest.py",
  line 223, in __init__
    workflow_jobs = self.jobs()
                    ^^^^^^^^^^^
  File
  "/Users/asullivan/backblaze/github_repos/boardwalk/test/server-client/pylib/regression_svreng_608.py",
  line 25, in jobs
    ZabbixEnterMaintenance({"zabbix_api_token": zabbix_api_token}),
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: TaskJob.__init__() takes 1 positional argument but 2 were given
asullivan@MBP-NT9RPG2XV7 server-client % ========
"""

from __future__ import annotations

from boardwalk import Job, PlaybookJob, TaskJob, Workflow, Workspace, WorkspaceConfig, path

zabbix_api_token = "NotARealToken"

__all__ = [
    "TaskJobWithOptionsShouldSucceedWorkspace",
    "PlaybookJobWithOptionsShouldSucceedWorkspace",
    "TaskJobWithPreconditionsShouldSucceedIfHostIsMacOSXWorkspace",
    "TaskJobWithPreconditionsShouldBeSkippedIfHostIsMacOSXWorkspace",
]


class TaskJobWithOptionsShouldSucceedWorkspace(Workspace):
    def config(self):
        return WorkspaceConfig(
            default_sort_order="ascending",
            host_pattern="localhost",
            workflow=TaskJobWithOptionsShouldSucceedWorkflow(),
        )


class PlaybookJobWithOptionsShouldSucceedWorkspace(Workspace):
    def config(self):
        return WorkspaceConfig(
            default_sort_order="ascending",
            host_pattern="localhost",
            workflow=PlaybookJobWithOptionsShouldSucceedWorkflow(),
        )


class TaskJobWithPreconditionsShouldSucceedIfHostIsMacOSXWorkspace(Workspace):
    def config(self):
        return WorkspaceConfig(
            default_sort_order="ascending",
            host_pattern="localhost",
            workflow=TaskJobWithPreconditionsShouldSucceedIfHostIsMacOSXWorkflow(),
        )


class TaskJobWithPreconditionsShouldBeSkippedIfHostIsMacOSXWorkspace(Workspace):
    def config(self):
        return WorkspaceConfig(
            default_sort_order="ascending",
            host_pattern="localhost",
            workflow=TaskJobWithPreconditionsShouldBeSkippedIfHostIsMacOSXWorkflow(),
        )


class TaskJobWithOptionsShouldSucceedWorkflow(Workflow):
    def jobs(self):
        return (
            TaskJobWithOption({"zabbix_api_token": zabbix_api_token}),
            DeprecatedJobWithOption({"zabbix_api_token": zabbix_api_token}),
        )

    def exit_jobs(self):
        return (TaskJobWithOption({"zabbix_api_token": zabbix_api_token}),)


class TaskJobWithPreconditionsShouldSucceedIfHostIsMacOSXWorkflow(Workflow):
    def jobs(self):
        return (TaskJobWithPreconditionsShouldSucceedIfHostIsMacOSX({"target_version": 9001}),)

    def exit_jobs(self):
        return (TaskJobWithPreconditionsShouldSucceedIfHostIsMacOSX({"target_version": 9001}),)


class TaskJobWithPreconditionsShouldBeSkippedIfHostIsMacOSXWorkflow(Workflow):
    def jobs(self):
        return (TaskJobWithPreconditionsShouldSucceedIfHostIsMacOSX({"target_version": 1}),)

    def exit_jobs(self):
        return (TaskJobWithPreconditionsShouldSucceedIfHostIsMacOSX({"target_version": 1}),)


class TaskJobWithPreconditionsShouldSucceedIfHostIsMacOSX(TaskJob):
    def required_options(self):
        return "target_version"

    def preconditions(self, facts: dict[str, str], inventory_vars: dict[str, str]):
        return facts["ansible_distribution"] == "MacOSX" and int(facts["ansible_distribution_major_version"]) < int(
            self.options["target_version"]
        )

    def tasks(self):
        return [
            {"set_fact": {"target_version": self.options["target_version"]}},
            {
                "ansible.builtin.debug": {
                    "msg": r"Your version of {{ ansible_distribution }} {{ ansible_distribution_major_version }} is less than the targeted version of {{ target_version }}, so you get to see this message!"
                }
            },
        ]


class PlaybookJobWithOptionsShouldSucceedWorkflow(Workflow):
    def jobs(self):
        return (TestPlaybookJobEchoVariable({"boardwalk_playbookjob_test_variable": zabbix_api_token}),)

    def exit_jobs(self):
        return (TestPlaybookJobEchoVariable({"boardwalk_playbookjob_test_variable": zabbix_api_token}),)


class DeprecatedJobWithOption(Job):
    def required_options(self) -> tuple[str]:
        return ("zabbix_api_token",)

    def tasks(self):
        return [
            {"set_fact": {"zabbix_api_token": self.options["zabbix_api_token"]}},
            {"ansible.builtin.debug": {"msg": r"{{ zabbix_api_token }}"}},
        ]


class TaskJobWithOption(TaskJob):
    def required_options(self) -> tuple[str]:
        return ("zabbix_api_token",)

    def tasks(self):
        return [
            {"set_fact": {"zabbix_api_token": self.options["zabbix_api_token"]}},
            {"ansible.builtin.debug": {"msg": r"{{ zabbix_api_token }}"}},
        ]


class TestPlaybookJobEchoVariable(PlaybookJob):
    def required_options(self) -> tuple[str]:
        return ("boardwalk_playbookjob_test_variable",)

    def tasks(self):
        return [
            {"ansible.builtin.import_playbook": path("playbooks/playbook-job-test-echo-variable.yml")},
        ]
