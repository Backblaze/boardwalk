import json
import re
from datetime import UTC, datetime, timedelta

import boardwalkd.server as server
from boardwalkd.dashboard import DashboardFilters, build_dashboard
from boardwalkd.snapshot import load_inventory_context, sanitize_status_snapshot, seed_snapshot_workspaces
from boardwalkd.state import State, WorkspaceState


def raw_status_snapshot(now: datetime):
    return {
        "workspaces": [
            {
                "name": "active_workspace_name",
                "semaphores": {
                    "caught": True,
                    "clear_remote_mutex_requested": False,
                    "clear_remote_state_requested": False,
                    "has_mutex": True,
                },
                "details": {
                    "current_host": "node-alpha-a",
                    "deployment_number": "50321",
                    "deployment_url": "https://jenkins.example/job/boardwalk/50321/",
                    "deployment_user": "operator1",
                    "deployment_user_email": "operator1@example.com",
                    "host_pattern": "nodes_alpha:nodes_beta",
                    "ui_group": "alpha",
                    "workflow": "NodeUpgrade",
                    "worker_command": "run",
                    "worker_hostname": "worker-prod-01",
                    "worker_limit": "node-alpha-a",
                    "worker_username": "operator1",
                    "worker": "operator1@worker-prod-01",
                    "worker_connected": True,
                },
                "last_seen": (now - timedelta(seconds=3)).isoformat(),
            },
            {
                "name": "old_workspace_name",
                "semaphores": {"caught": False, "has_mutex": False},
                "details": {
                    "current_host": "",
                    "host_pattern": "nodes_theta",
                    "ui_group": "",
                    "workflow": "StaleCleanup",
                    "worker_hostname": "worker-prod-02",
                    "worker_username": "operator2",
                    "worker_connected": False,
                },
                "last_seen": (now - timedelta(days=9)).isoformat(),
            },
            {
                "name": "multi_group_workspace_name",
                "semaphores": {"caught": False, "has_mutex": True},
                "details": {
                    "current_host": "",
                    "host_pattern": "nodes_alpha:nodes_beta",
                    "workflow": "MultiGroupCanary",
                    "worker_hostname": "worker-prod-03",
                    "worker_username": "operator2",
                    "worker_connected": True,
                },
                "last_seen": (now - timedelta(seconds=2)).isoformat(),
            },
        ]
    }


def test_sanitize_status_snapshot_redacts_sensitive_identifiers_but_preserves_operational_shape():
    now = datetime(2026, 6, 3, tzinfo=UTC)

    sanitized = sanitize_status_snapshot(raw_status_snapshot(now), now=now)

    assert sanitized["snapshot_format"] == "boardwalkd-status-snapshot-v1"
    assert sanitized["captured_at"] == "2026-06-03T00:00:00+00:00"
    assert [workspace["name"] for workspace in sanitized["workspaces"]] == [
        "snapshot_alpha_001",
        "snapshot_theta_002",
        "snapshot_multi_group_003",
    ]
    assert sanitized["workspaces"][0]["details"]["ui_group"] == "alpha"
    assert sanitized["workspaces"][0]["details"]["current_host"] == "snapshot-host-alpha-001"
    assert sanitized["workspaces"][0]["details"]["host_pattern"] == "pattern-alpha-001:pattern-beta-001"
    assert sanitized["workspaces"][0]["details"]["deployment_number"] == "snapshot-build-001"
    assert sanitized["workspaces"][0]["details"]["deployment_url"] == "https://snapshot.invalid/deployment/001/"
    assert sanitized["workspaces"][0]["details"]["worker_limit"] == "snapshot-host-alpha-001"
    assert sanitized["workspaces"][0]["worker_connected"] is True
    assert sanitized["workspaces"][1]["details"]["ui_group"] == "theta"
    assert sanitized["workspaces"][1]["last_seen_age_seconds"] == 9 * 24 * 60 * 60
    assert sanitized["workspaces"][2]["details"]["ui_group"] == "Multi-group"

    text = repr(sanitized)
    assert "active_workspace_name" not in text
    assert "old_workspace_name" not in text
    assert "multi_group_workspace_name" not in text
    assert "node-alpha-a" not in text
    assert "nodes_alpha" not in text
    assert "50321" not in text
    assert "worker-prod-01" not in text
    assert "operator1" not in text
    assert all(re.fullmatch(r"\w+", workspace["name"]) for workspace in sanitized["workspaces"])


def test_sanitize_status_snapshot_can_preserve_identifiers_for_private_local_replay():
    now = datetime(2026, 6, 3, tzinfo=UTC)

    snapshot = sanitize_status_snapshot(raw_status_snapshot(now), now=now, preserve_identifiers=True)

    assert [workspace["name"] for workspace in snapshot["workspaces"]] == [
        "active_workspace_name",
        "old_workspace_name",
        "multi_group_workspace_name",
    ]
    assert snapshot["workspaces"][0]["details"]["worker_hostname"] == "worker-prod-01"
    assert snapshot["workspaces"][0]["details"]["worker_username"] == "operator1"
    assert snapshot["workspaces"][0]["details"]["deployment_user"] == "operator1"
    assert snapshot["workspaces"][1]["details"]["ui_group"] == "theta"
    assert snapshot["workspaces"][2]["details"]["ui_group"] == "Multi-group"
    assert "worker_connected" not in snapshot["workspaces"][0]["details"]


def test_sanitize_status_snapshot_does_not_guess_group_from_numeric_storage_pattern():
    now = datetime(2026, 6, 3, tzinfo=UTC)
    snapshot = sanitize_status_snapshot(
        {
            "workspaces": [
                {
                    "name": "storage_workspace",
                    "semaphores": {"caught": False, "has_mutex": True},
                    "details": {
                        "host_pattern": "storage_001:!storage_nonprod",
                        "worker_hostname": "worker-prod-01",
                        "worker_username": "operator1",
                        "worker_connected": True,
                    },
                    "last_seen": now.isoformat(),
                }
            ]
        },
        now=now,
        preserve_identifiers=True,
    )

    workspace = snapshot["workspaces"][0]
    assert workspace["name"] == "storage_workspace"
    assert workspace["details"]["host_pattern"] == "storage_001:!storage_nonprod"
    assert workspace["details"]["ui_group"] == ""


def test_sanitize_status_snapshot_can_derive_group_from_inventory_group_ancestry():
    now = datetime(2026, 6, 3, tzinfo=UTC)
    inventory = {
        "_meta": {"hostvars": {}},
        "storage_001": {"hosts": ["node-alpha-a"]},
        "storage_002": {"hosts": ["node-beta-a"]},
        "storage_alpha": {"children": ["storage_001"]},
        "storage_beta": {"children": ["storage_002"]},
    }

    snapshot = sanitize_status_snapshot(
        {
            "workspaces": [
                {
                    "name": "alpha-storage",
                    "semaphores": {"caught": False, "has_mutex": True},
                    "details": {
                        "host_pattern": "storage_001:!storage_nonprod",
                        "worker_connected": True,
                    },
                    "last_seen": now.isoformat(),
                },
                {
                    "name": "beta-storage",
                    "semaphores": {"caught": False, "has_mutex": True},
                    "details": {
                        "host_pattern": "storage_002:!storage_nonprod",
                        "worker_connected": True,
                    },
                    "last_seen": now.isoformat(),
                },
            ]
        },
        now=now,
        preserve_identifiers=True,
        inventory=inventory,
    )

    assert snapshot["workspaces"][0]["details"]["ui_group"] == "alpha"
    assert snapshot["workspaces"][1]["details"]["ui_group"] == "beta"


def test_sanitize_status_snapshot_marks_multi_group_when_inventory_ancestry_has_multiple_groups():
    now = datetime(2026, 6, 3, tzinfo=UTC)
    inventory = {
        "_meta": {"hostvars": {}},
        "storage_001": {"hosts": ["node-alpha-a"]},
        "storage_002": {"hosts": ["node-beta-a"]},
        "storage_alpha": {"children": ["storage_001"]},
        "storage_beta": {"children": ["storage_002"]},
    }

    snapshot = sanitize_status_snapshot(
        {
            "workspaces": [
                {
                    "name": "multi-storage",
                    "semaphores": {"caught": False, "has_mutex": True},
                    "details": {
                        "host_pattern": "storage_001:storage_002:!storage_nonprod",
                        "worker_connected": True,
                    },
                    "last_seen": now.isoformat(),
                }
            ]
        },
        now=now,
        preserve_identifiers=True,
        inventory=inventory,
    )

    assert snapshot["workspaces"][0]["details"]["ui_group"] == "Multi-group"


def test_load_inventory_context_reads_inventory_json(tmp_path):
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps({"_meta": {"hostvars": {}}, "storage_alpha": {"children": []}}))
    inventory = load_inventory_context(path)

    assert inventory is not None
    assert inventory["storage_alpha"]["children"] == []


def test_seed_snapshot_workspaces_replays_sanitized_status_into_local_state(tmp_path):
    captured_at = datetime(2026, 6, 3, tzinfo=UTC)
    replay_now = datetime(2026, 6, 4, tzinfo=UTC)
    sanitized = sanitize_status_snapshot(raw_status_snapshot(captured_at), now=captured_at)
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(sanitized))
    state = State()

    seeded = seed_snapshot_workspaces(state, path, now=replay_now)
    dashboard = build_dashboard(state.workspaces, DashboardFilters(), now=replay_now)

    assert seeded is True
    assert set(state.workspaces) == {"snapshot_alpha_001", "snapshot_theta_002", "snapshot_multi_group_003"}
    assert state.workspaces["snapshot_alpha_001"].details.current_host == "snapshot-host-alpha-001"
    assert state.workspaces["snapshot_alpha_001"].semaphores.caught is True
    assert state.workspaces["snapshot_alpha_001"].last_seen is not None
    assert state.workspaces["snapshot_alpha_001"].last_seen > replay_now
    assert state.workspaces["snapshot_theta_002"].last_seen == replay_now - timedelta(days=9)
    assert [(group.label, group.count) for group in dashboard.groups] == [
        ("All", 3),
        ("alpha", 1),
        ("Multi-group", 1),
        ("theta", 1),
    ]
    assert [(lane.label, [row.status for row in lane.rows]) for lane in dashboard.lanes] == [
        ("Active workspaces", ["running"]),
        ("Caught workspaces", ["caught"]),
        ("Inactive workspaces", ["stale"]),
    ]
    assert all("Sanitized production status snapshot" in row.latest_event for row in dashboard.rows)


def test_seed_snapshot_workspaces_sanitizes_raw_status_before_persisting(tmp_path):
    now = datetime(2026, 6, 3, tzinfo=UTC)
    path = tmp_path / "raw.json"
    path.write_text(json.dumps(raw_status_snapshot(now)))
    state = State()

    seeded = seed_snapshot_workspaces(state, path, now=now)

    assert seeded is True
    assert "active_workspace_name" not in state.workspaces
    assert state.workspaces["snapshot_alpha_001"].details.worker_hostname == "snapshot-worker-alpha-001"
    assert state.workspaces["snapshot_theta_002"].details.ui_group == "theta"


def test_seed_snapshot_workspaces_does_not_overwrite_existing_state(tmp_path):
    path = tmp_path / "snapshot.json"
    path.write_text('{"workspaces": []}')
    state = State(workspaces={"existing": WorkspaceState()})

    seeded = seed_snapshot_workspaces(state, path)

    assert seeded is False
    assert list(state.workspaces) == ["existing"]


def test_development_server_does_not_seed_demo_without_demo_flag(monkeypatch):
    state = State()
    monkeypatch.setattr(server, "state", state)

    server.make_app(
        auth_expire_days=14,
        auth_login_slack_notify=False,
        auth_method="anonymous",
        develop=True,
        host_header_pattern=re.compile(r"localhost(:[0-9]+)?"),
        owner="anonymous@example.com",
        slack_bot_token=None,
        slack_error_advice_rules=[],
        slack_error_webhook_url="",
        slack_webhook_url="",
        url="http://localhost:8888",
        workspace_status_json=True,
    )

    assert state.workspaces == {}


def test_server_uses_demo_seed_when_requested(monkeypatch):
    state = State()
    monkeypatch.setattr(server, "state", state)

    server.make_app(
        auth_expire_days=14,
        auth_login_slack_notify=False,
        auth_method="anonymous",
        develop=False,
        demo=True,
        host_header_pattern=re.compile(r"localhost(:[0-9]+)?"),
        owner="anonymous@example.com",
        slack_bot_token=None,
        slack_error_advice_rules=[],
        slack_error_webhook_url="",
        slack_webhook_url="",
        url="http://localhost:8888",
        workspace_status_json=True,
    )

    assert "nodes_alpha_group_upgrade" in state.workspaces


def test_development_server_uses_snapshot_seed_instead_of_synthetic_demo_seed(tmp_path, monkeypatch):
    now = datetime(2026, 6, 3, tzinfo=UTC)
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(sanitize_status_snapshot(raw_status_snapshot(now), now=now)))
    state = State()
    monkeypatch.setattr(server, "state", state)

    server.make_app(
        auth_expire_days=14,
        auth_login_slack_notify=False,
        auth_method="anonymous",
        develop=True,
        develop_snapshot_path=str(path),
        host_header_pattern=re.compile(r"localhost(:[0-9]+)?"),
        owner="anonymous@example.com",
        slack_bot_token=None,
        slack_error_advice_rules=[],
        slack_error_webhook_url="",
        slack_webhook_url="",
        url="http://localhost:8888",
        workspace_status_json=True,
    )

    assert set(state.workspaces) == {"snapshot_alpha_001", "snapshot_theta_002", "snapshot_multi_group_003"}
    assert "nodes_alpha_group_upgrade" not in state.workspaces
