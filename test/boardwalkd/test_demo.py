from boardwalkd.dashboard import DashboardFilters, build_dashboard
from boardwalkd.demo import seed_development_workspaces
from boardwalkd.state import State, WorkspaceState


def test_seed_development_workspaces_adds_clickable_mock_data_to_empty_state():
    state = State()

    seeded = seed_development_workspaces(state)
    dashboard = build_dashboard(state.workspaces, DashboardFilters(group="alpha", status="caught"))

    assert seeded is True
    assert len(state.workspaces) >= 10
    assert {ws.details.ui_group or "Ungrouped" for ws in state.workspaces.values()} >= {
        "alpha",
        "beta",
        "delta",
        "gamma",
        "omega",
        "theta",
        "Ungrouped",
    }
    assert any(ws.details.current_host for ws in state.workspaces.values())
    assert any(ws.semaphores.caught for ws in state.workspaces.values())
    assert any(ws.details.deployment_number for ws in state.workspaces.values())
    assert any(not ws.details.deployment_number for ws in state.workspaces.values())
    assert any(len(name) > 40 for name in state.workspaces)
    assert any(len(ws.details.current_host) > 40 for ws in state.workspaces.values())
    assert any(row.can_request_remote_cleanup for row in dashboard.rows)
    assert any(row.status == "stale" for row in build_dashboard(state.workspaces, DashboardFilters()).rows)


def test_seed_development_workspaces_uses_generic_fictional_host_patterns():
    state = State()

    seed_development_workspaces(state)
    details = {name: workspace.details for name, workspace in state.workspaces.items()}

    assert details["nodes_alpha_group_upgrade"].host_pattern == "nodes_alpha"
    assert details["nodes_alpha_group_upgrade"].current_host == "node-alpha-a"
    assert details["nodes_alpha_group_upgrade"].ui_group == "alpha"

    assert details["nodes_beta_group_upgrade"].host_pattern == "nodes_beta"
    assert details["nodes_beta_group_upgrade"].current_host == "node-beta-a"
    assert details["nodes_beta_group_upgrade"].ui_group == "beta"

    assert details["nodes_multi_group_beta_current"].host_pattern == "nodes_alpha:nodes_beta:nodes_gamma"
    assert details["nodes_multi_group_beta_current"].current_host == "node-beta-a"
    assert details["nodes_multi_group_beta_current"].ui_group == "beta"

    assert details["storage_multi_group_alpha_current"].host_pattern == "storage_alpha:storage_beta:storage_gamma"
    assert details["storage_multi_group_alpha_current"].current_host == "storage-alpha-a"
    assert details["storage_multi_group_alpha_current"].ui_group == "alpha"
    assert details["stale_deletable_workspace"].host_pattern == "nodes_omega"
    assert details["stale_deletable_workspace"].current_host == "node-omega-b"
    assert state.workspaces["stale_deletable_workspace"].semaphores.has_mutex is False
    assert details["stale_mutexed_workspace"].host_pattern == "nodes_theta"
    assert details["stale_mutexed_workspace"].current_host == "node-theta-b"


def test_seed_development_workspaces_sorts_demo_rows_into_group_tabs():
    state = State()

    seed_development_workspaces(state)
    dashboard = build_dashboard(state.workspaces, DashboardFilters())

    assert [group.label for group in dashboard.groups] == [
        "All",
        "alpha",
        "beta",
        "delta",
        "gamma",
        "host_progress",
        "large_volume_of_workspaces",
        "omega",
        "theta",
        "Ungrouped",
    ]
    for group in ["alpha", "beta", "delta", "gamma", "omega", "theta"]:
        group_dashboard = build_dashboard(state.workspaces, DashboardFilters(group=group))
        assert group_dashboard.rows
        assert {row.group for row in group_dashboard.rows} == {group}


def test_seed_development_workspaces_keeps_most_demo_rows_deletable_in_edit_mode():
    state = State()

    seed_development_workspaces(state)

    assert state.workspaces["nodes_alpha_group_upgrade"].semaphores.has_mutex is False
    assert state.workspaces["very_very_long_workspace_name_for_fit_testing_and_demo"].semaphores.has_mutex is False
    assert state.workspaces["stale_mutexed_workspace"].semaphores.has_mutex is True


def test_seed_development_workspaces_does_not_overwrite_existing_state():
    state = State(workspaces={"real": WorkspaceState()})

    seeded = seed_development_workspaces(state)

    assert seeded is False
    assert list(state.workspaces) == ["real"]
