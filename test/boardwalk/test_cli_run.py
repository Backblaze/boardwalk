from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from boardwalk import Workflow, WorkspaceConfig, cli_run
from boardwalk.ansible import ansible_runner_run_tasks
from boardwalk.cli_run import (
    build_workspace_details,
    resolve_workspace_ui_group,
    workspace_event_for_ansible_task_start,
)
from boardwalk.manifest import JobTypes


class EmptyWorkflow(Workflow):
    def jobs(self):
        return ()


class FakeBoardwalkdClient:
    def __init__(self):
        self.details = []
        self.events = []

    def post_details(self, details):
        self.details.append(details)

    def queue_event(self, event, broadcast=False):
        self.events.append((event, broadcast))


class FakeHost:
    def __init__(self, name):
        self.name = name

    def release(self, become_password=None, check=False):
        return None


def context_with_limit(limit_value) -> Any:
    return SimpleNamespace(params={"limit": limit_value})


def workspace_with_config(cfg) -> Any:
    return SimpleNamespace(
        name="UpgradeNodes",
        cfg=cfg,
    )


def test_resolve_workspace_ui_group_prefers_explicit_group():
    cfg = WorkspaceConfig(
        host_pattern="nodes",
        workflow=EmptyWorkflow(),
        ui_group="net",
        ui_group_inventory_var="site_group",
    )
    workspace = workspace_with_config(cfg)

    group = resolve_workspace_ui_group(
        workspace=workspace,
        current_host="node-alpha-a",
        inventory_vars={"node-alpha-a": {"site_group": "alpha"}},
    )

    assert group == "net"


def test_resolve_workspace_ui_group_reads_inventory_var_for_current_host():
    cfg = WorkspaceConfig(
        host_pattern="nodes",
        workflow=EmptyWorkflow(),
        ui_group_inventory_var="site_group",
    )
    workspace = workspace_with_config(cfg)

    group = resolve_workspace_ui_group(
        workspace=workspace,
        current_host="node-alpha-a",
        inventory_vars={"node-alpha-a": {"site_group": "alpha"}},
    )

    assert group == "alpha"


def test_resolve_workspace_ui_group_returns_blank_without_host_or_var():
    cfg = WorkspaceConfig(host_pattern="nodes", workflow=EmptyWorkflow())
    workspace = workspace_with_config(cfg)

    assert resolve_workspace_ui_group(workspace=workspace) == ""


def test_resolve_workspace_ui_group_ignores_inventory_vars_when_no_var_configured():
    cfg = WorkspaceConfig(host_pattern="nodes", workflow=EmptyWorkflow())
    workspace = workspace_with_config(cfg)

    group = resolve_workspace_ui_group(
        workspace=workspace,
        current_host="node-alpha-a",
        inventory_vars={"node-alpha-a": {"unrelated_inventory_value": "alpha"}},
    )

    assert group == ""


def test_build_workspace_details_includes_existing_fields_current_host_and_derived_group(monkeypatch):
    monkeypatch.setattr(cli_run.socket, "gethostname", lambda: "worker-host")
    monkeypatch.setattr(cli_run.getpass, "getuser", lambda: "worker-user")
    monkeypatch.setenv("BUILD_URL", "https://build.example/job/1")
    monkeypatch.setenv("BUILD_TAG", "build-tag")
    monkeypatch.setenv("JOB_NAME", "boardwalk-refresh")
    monkeypatch.setenv("BUILD_NUMBER", "42")
    monkeypatch.setenv("BUILD_USER", "Builder")
    monkeypatch.setenv("BUILD_USER_ID", "builder-id")
    monkeypatch.setenv("BUILD_USER_EMAIL", "builder@example.com")
    cfg = WorkspaceConfig(
        host_pattern="nodes",
        workflow=EmptyWorkflow(),
        ui_group_inventory_var="site_group",
    )
    workspace = workspace_with_config(cfg)

    details = build_workspace_details(
        workspace=workspace,
        ctx=context_with_limit("node-alpha-a"),
        current_host="node-alpha-a",
        inventory_vars={"node-alpha-a": {"site_group": "alpha"}},
    )

    assert details.deployment_url == "https://build.example/job/1"
    assert details.deployment_name == "boardwalk-refresh"
    assert details.deployment_number == "42"
    assert details.deployment_tag == "build-tag"
    assert details.deployment_user == "Builder"
    assert details.deployment_user_id == "builder-id"
    assert details.deployment_user_email == "builder@example.com"
    assert details.host_pattern == "nodes"
    assert details.workflow == "EmptyWorkflow"
    assert details.worker_command in {"check", "run"}
    assert details.worker_hostname == "worker-host"
    assert details.worker_limit == "node-alpha-a"
    assert details.worker_username == "worker-user"
    assert details.current_host == "node-alpha-a"
    assert details.ui_group == "alpha"


def test_workspace_event_for_ansible_task_start_formats_role_task_name():
    event = workspace_event_for_ansible_task_start(
        hostname="node-alpha-a",
        event_data={
            "event": "playbook_on_task_start",
            "event_data": {
                "role": "network_setup",
                "task": "Set sysctl values",
            },
        },
    )

    assert event is not None
    assert event.severity == "info"
    assert event.message == "node-alpha-a: Running Ansible task network_setup : Set sysctl values"


def test_workspace_event_for_ansible_task_start_ignores_non_task_start_events():
    event = workspace_event_for_ansible_task_start(
        hostname="node-alpha-a",
        event_data={
            "event": "runner_on_ok",
            "event_data": {
                "role": "network_setup",
                "task": "Set sysctl values",
            },
        },
    )

    assert event is None


def test_run_workflow_posts_current_host_details_when_each_host_starts(monkeypatch):
    client = FakeBoardwalkdClient()
    monkeypatch.setattr(cli_run, "boardwalkd_client", client)
    monkeypatch.setattr(cli_run, "handle_workflow_catch", lambda workspace, host: None)
    monkeypatch.setattr(cli_run, "lock_remote_host", lambda host: None)
    monkeypatch.setattr(cli_run, "directly_confirm_host_preconditions", lambda host, inventory_vars, workspace: True)
    monkeypatch.setattr(cli_run, "execute_host_workflow", lambda host, workspace, verbosity: None)
    monkeypatch.setattr(cli_run.socket, "gethostname", lambda: "worker-host")
    monkeypatch.setattr(cli_run.getpass, "getuser", lambda: "worker-user")
    cfg = WorkspaceConfig(
        host_pattern="nodes",
        workflow=EmptyWorkflow(),
        ui_group_inventory_var="site_group",
    )
    workspace = workspace_with_config(cfg)
    inventory_vars = {
        "node-alpha-a": {"site_group": "alpha"},
        "node-beta-a": {"site_group": "beta"},
    }

    cli_run.run_workflow(
        hosts=cast(Any, [FakeHost("node-alpha-a"), FakeHost("node-beta-a")]),
        inventory_vars=inventory_vars,
        workspace=workspace,
        verbosity=0,
        ctx=context_with_limit("node-*"),
    )

    assert [details.current_host for details in client.details] == [
        "node-alpha-a",
        "node-beta-a",
    ]
    assert [details.ui_group for details in client.details] == ["alpha", "beta"]


def test_ansible_runner_run_tasks_passes_event_handler_to_ansible_runner(monkeypatch, tmp_path):
    captured = {}

    def fake_get_ws():
        return SimpleNamespace(path=tmp_path)

    def fake_run(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(rc=0, events=[])

    def event_handler(event_data):
        return True

    monkeypatch.setattr("boardwalk.manifest.get_ws", fake_get_ws)
    monkeypatch.setattr("boardwalk.ansible.ansible_runner.run", fake_run)
    monkeypatch.chdir(Path("/"))

    ansible_runner_run_tasks(
        hosts="node-alpha-a",
        invocation_msg="main_TASK_Job_StopServiceJob",
        job_type=JobTypes.TASK,
        tasks=[{"name": "Stop service", "ansible.builtin.debug": {"msg": "stop"}}],
        event_handler=event_handler,
    )

    assert captured["event_handler"] is event_handler
