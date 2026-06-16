import hashlib
from collections import deque
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from pydantic import ValidationError
from tornado.template import Loader

import boardwalkd.server as boardwalkd_server
from boardwalkd.dashboard import (
    DashboardFilters,
    action_url,
    build_dashboard,
    canonical_url,
    latest_event,
    partial_url,
    query_url,
    sort_url,
    source_for_workspace,
    status_for_workspace,
    worker_connected,
)
from boardwalkd.protocol import WorkspaceDetails, WorkspaceEvent, WorkspaceSemaphores
from boardwalkd.server import (
    workspace_client_details_event_message,
    workspace_client_details_event_should_log,
)
from boardwalkd.slack_error_advice import SlackErrorAdviceRule
from boardwalkd.state import WorkspaceState
from boardwalkd.utils import is_workspace_active


def ws(
    *,
    group="",
    current_host="",
    caught=False,
    worker_limit="all",
    deployment_number="",
    deployment_url="",
    deployment_user="",
    worker_hostname="worker-01",
    worker_username="operator",
    has_mutex=True,
    last_seen=None,
    events=None,
):
    return WorkspaceState(
        details=WorkspaceDetails(
            current_host=current_host,
            deployment_number=deployment_number,
            deployment_url=deployment_url,
            deployment_user=deployment_user,
            host_pattern="nodes",
            ui_group=group,
            worker_command="run",
            worker_hostname=worker_hostname,
            worker_limit=worker_limit,
            worker_username=worker_username,
            workflow="UpgradeWorkflow",
        ),
        events=deque(events or []),
        last_seen=last_seen,
        semaphores=WorkspaceSemaphores(caught=caught, has_mutex=has_mutex),
    )


def lane_names(dashboard):
    return {lane.label: [row.name for row in lane.rows] for lane in dashboard.lanes}


def test_workspace_details_accepts_ui_group_and_current_host():
    details = WorkspaceDetails(ui_group="alpha", current_host="node-alpha-a")

    assert details.ui_group == "alpha"
    assert details.current_host == "node-alpha-a"


def test_workspace_details_defaults_new_ui_fields_to_blank_strings():
    details = WorkspaceDetails()

    assert details.ui_group == ""
    assert details.current_host == ""


def test_workspace_details_still_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        WorkspaceDetails.model_validate({"made_up": "nope"})


def test_workspace_client_details_event_logs_initial_client_details():
    details = WorkspaceDetails(
        workflow="UpgradeWorkflow",
        worker_username="operator",
        worker_hostname="worker-01",
        host_pattern="nodes",
        worker_limit="node-alpha-a",
        worker_command="run",
    )

    assert workspace_client_details_event_should_log(None, details) is True
    assert workspace_client_details_event_message(details) == (
        "Workspace client details:"
        " Workflow: UpgradeWorkflow,"
        " Worker: operator@worker-01,"
        " Host Pattern: nodes,"
        " Limit Pattern: node-alpha-a,"
        " Command: run"
    )


def test_workspace_client_details_event_skips_current_host_only_update():
    old_details = WorkspaceDetails(
        workflow="UpgradeWorkflow",
        worker_username="operator",
        worker_hostname="worker-01",
        host_pattern="nodes",
        worker_limit="node-*",
        worker_command="run",
    )
    new_details = old_details.model_copy(update={"current_host": "node-alpha-a", "ui_group": "alpha"})

    assert workspace_client_details_event_should_log(old_details, new_details) is False


def test_build_dashboard_groups_counts_and_default_rows_follow_lane_sorting():
    rows = {
        "workspace_beta": ws(group="beta", current_host="node-beta"),
        "workspace_alpha": ws(group="alpha", current_host="node-alpha"),
        "workspace_gamma": ws(current_host="node-ungrouped"),
    }

    dashboard = build_dashboard(rows, DashboardFilters())

    assert [group.label for group in dashboard.groups] == ["All", "alpha", "beta", "Ungrouped"]
    assert [group.count for group in dashboard.groups] == [3, 1, 1, 1]
    assert [row.name for row in dashboard.rows] == ["workspace_alpha", "workspace_beta", "workspace_gamma"]


def test_build_dashboard_filters_by_selected_group():
    rows = {
        "workspace_beta": ws(group="beta", current_host="node-beta"),
        "workspace_alpha": ws(group="alpha", current_host="node-alpha"),
    }

    dashboard = build_dashboard(rows, DashboardFilters(group="alpha"))

    assert [row.name for row in dashboard.rows] == ["workspace_alpha"]
    assert [group.active for group in dashboard.groups] == [False, True, False]


def test_build_dashboard_group_counts_follow_current_non_group_filters():
    now = datetime.now(UTC)
    rows = {
        "alpha_caught": ws(group="alpha", caught=True, current_host="node-alpha"),
        "alpha_running": ws(group="alpha", last_seen=now, current_host="node-alpha-running"),
        "theta_running": ws(group="theta", last_seen=now, current_host="node-theta"),
    }

    dashboard = build_dashboard(rows, DashboardFilters(group="theta", status="caught"), now=now)

    assert [(group.label, group.count) for group in dashboard.groups] == [
        ("All", 1),
        ("alpha", 1),
        ("theta", 0),
    ]
    assert dashboard.rows == []


def test_build_dashboard_filters_search_across_name_host_limit_user_worker_and_build_label():
    rows = {
        "workspace_a": ws(group="alpha", current_host="node-alpha-a", worker_limit="node-*"),
        "workspace_b": ws(group="alpha", deployment_number="12345", deployment_user="operator-a"),
        "workspace_c": ws(group="net", worker_hostname="worker-special", worker_username="operator-net"),
    }

    assert [row.name for row in build_dashboard(rows, DashboardFilters(search="alpha-a")).rows] == ["workspace_a"]
    assert [
        row.name
        for row in build_dashboard(
            rows,
            DashboardFilters(search="build 12345"),
            jenkins_job_url="https://jenkins.example/job/boardwalk/",
        ).rows
    ] == ["workspace_b"]
    assert [row.name for row in build_dashboard(rows, DashboardFilters(search="operator-a")).rows] == ["workspace_b"]
    assert [row.name for row in build_dashboard(rows, DashboardFilters(search="worker-special")).rows] == [
        "workspace_c"
    ]


def test_build_dashboard_filters_by_status_and_source():
    now = datetime.now(UTC)
    deployment_url = "https://ci.example/build/standalone"
    rows = {
        "running_workspace": ws(group="alpha", last_seen=now),
        "jenkins_workspace": ws(group="alpha", deployment_number="12345"),
        "deployment_workspace": ws(group="alpha", deployment_url=deployment_url),
    }

    running = build_dashboard(rows, DashboardFilters(status="running"), now=now)
    jenkins = build_dashboard(
        rows,
        DashboardFilters(source="jenkins"),
        jenkins_job_url="https://jenkins.example/job/boardwalk/",
        now=now,
    )
    deployment = build_dashboard(
        rows,
        DashboardFilters(source="deployment"),
        jenkins_job_url="https://jenkins.example/job/boardwalk/",
        now=now,
    )

    assert [row.name for row in running.rows] == ["running_workspace"]
    assert [row.name for row in jenkins.rows] == ["jenkins_workspace"]
    assert [row.name for row in deployment.rows] == ["deployment_workspace"]


def test_build_dashboard_marks_status_latest_event_worker_connection_and_cleanup_eligibility():
    now = datetime.now(UTC)
    rows = {
        "caught_workspace": ws(
            group="alpha",
            caught=True,
            last_seen=now,
            events=[
                WorkspaceEvent(severity="info", message="older", create_time=now - timedelta(seconds=5)),
                WorkspaceEvent(severity="success", message="newer", create_time=now),
            ],
        ),
    }

    row = build_dashboard(rows, DashboardFilters(), now=now).rows[0]

    assert row.status == "caught"
    assert row.latest_event == "newer"
    assert row.worker_connected is True
    assert row.can_request_remote_cleanup is True


def test_status_latest_and_worker_connected_helpers_handle_idle_done_and_error_states():
    now = datetime.now(UTC)
    error_ws = ws(events=[WorkspaceEvent(severity="error", message="failed", create_time=now)])
    done_ws = ws(events=[WorkspaceEvent(severity="success", message="done", create_time=now)])
    old_ws = ws(last_seen=now - timedelta(seconds=11))
    stale_ws = ws(last_seen=now - timedelta(days=8))

    assert status_for_workspace(error_ws, now=now) == "error"
    assert status_for_workspace(done_ws, now=now) == "done"
    assert status_for_workspace(old_ws, now=now) == "idle"
    assert status_for_workspace(stale_ws, now=now) == "stale"
    assert worker_connected(old_ws, now=now) is False
    assert latest_event(done_ws) == "done"


def test_status_for_workspace_uses_latest_terminal_event_after_worker_disconnects():
    now = datetime.now(UTC)
    done_after_error = ws(
        has_mutex=False,
        last_seen=now - timedelta(minutes=5),
        events=[
            WorkspaceEvent(severity="error", message="older failure", create_time=now - timedelta(minutes=10)),
            WorkspaceEvent(severity="success", message="newer success", create_time=now - timedelta(minutes=1)),
        ],
    )

    assert status_for_workspace(done_after_error, now=now) == "done"


def test_status_for_workspace_treats_connected_worker_as_running_after_prior_error():
    now = datetime.now(UTC)
    running_ws = ws(
        last_seen=now,
        events=[
            WorkspaceEvent(severity="error", message="previous attempt failed", create_time=now - timedelta(minutes=5)),
            WorkspaceEvent(severity="info", message="Running main TASK job NetworkSetup", create_time=now),
        ],
    )

    assert status_for_workspace(running_ws, now=now) == "running"


def test_worker_stale_threshold_is_twenty_four_hours():
    now = datetime.now(UTC)
    recently_seen = ws(last_seen=now - timedelta(hours=23), has_mutex=False)
    stale_ws = ws(last_seen=now - timedelta(hours=25), has_mutex=False)

    assert status_for_workspace(recently_seen, now=now) == "idle"
    assert status_for_workspace(stale_ws, now=now) == "stale"


def test_build_dashboard_classifies_rows_into_operational_lanes():
    now = datetime.now(UTC)
    rows = {
        "active_running": ws(last_seen=now, current_host="node-active-running"),
        "active_previous_error": ws(
            last_seen=now,
            has_mutex=False,
            events=[WorkspaceEvent(severity="error", message="failed earlier", create_time=now - timedelta(minutes=4))],
        ),
        "caught_connected": ws(caught=True, last_seen=now, current_host="node-active-caught"),
        "inactive_error": ws(
            has_mutex=False,
            events=[WorkspaceEvent(severity="error", message="failed", create_time=now - timedelta(minutes=4))],
        ),
        "inactive_caught": ws(caught=True, last_seen=now - timedelta(minutes=2), has_mutex=False),
        "inactive_stale_mutex": ws(last_seen=now - timedelta(hours=25), has_mutex=True),
        "inactive_done": ws(
            has_mutex=False,
            events=[WorkspaceEvent(severity="success", message="done", create_time=now - timedelta(minutes=1))],
        ),
        "inactive_idle": ws(has_mutex=False),
        "inactive_stale": ws(last_seen=now - timedelta(hours=25), has_mutex=False),
    }

    dashboard = build_dashboard(rows, DashboardFilters(), now=now)

    assert lane_names(dashboard) == {
        "Active workspaces": ["active_running", "active_previous_error"],
        "Caught workspaces": ["caught_connected"],
        "Inactive workspaces": [
            "inactive_error",
            "inactive_caught",
            "inactive_stale_mutex",
            "inactive_stale",
            "inactive_idle",
            "inactive_done",
        ],
    }
    assert [row.name for row in dashboard.rows] == [
        "active_running",
        "active_previous_error",
        "caught_connected",
        "inactive_error",
        "inactive_caught",
        "inactive_stale_mutex",
        "inactive_stale",
        "inactive_idle",
        "inactive_done",
    ]


def test_build_dashboard_reuses_slack_error_advice_for_inactive_error_rows():
    now = datetime.now(UTC)
    rule = SlackErrorAdviceRule(
        name="Secret store auth expired",
        patterns=["status: 403", "invalid token"],
        message="Abort this CI job and start a fresh Boardwalk job.",
    )
    rows = {
        "auth_expired": ws(
            has_mutex=False,
            deployment_number="50321",
            events=[
                WorkspaceEvent(
                    severity="error",
                    message="status: 403; permission denied; invalid token",
                    create_time=now,
                )
            ],
        )
    }

    dashboard = build_dashboard(rows, DashboardFilters(), error_advice_rules=[rule], now=now)
    row = dashboard.rows[0]

    assert lane_names(dashboard) == {"Inactive workspaces": ["auth_expired"]}
    assert [(advice.name, advice.message) for advice in row.advice] == [
        ("Secret store auth expired", "Abort this CI job and start a fresh Boardwalk job.")
    ]


def test_build_dashboard_column_sorting_applies_inside_each_lane():
    now = datetime.now(UTC)
    rows = {
        "zz_deploy": ws(
            last_seen=now,
            current_host="node-c",
            deployment_url="https://ci.example/deploy/9",
            events=[WorkspaceEvent(severity="info", message="newest", create_time=now)],
        ),
        "aa_jenkins": ws(
            last_seen=now,
            current_host="node-a",
            deployment_number="50321",
            events=[WorkspaceEvent(severity="info", message="middle", create_time=now - timedelta(minutes=2))],
        ),
        "mm_local": ws(
            last_seen=now,
            current_host="node-b",
            events=[WorkspaceEvent(severity="info", message="oldest", create_time=now - timedelta(minutes=5))],
        ),
    }

    assert lane_names(
        build_dashboard(
            rows,
            DashboardFilters(sort="workspace"),
            jenkins_job_url="https://jenkins.example/job/boardwalk/",
            now=now,
        )
    )["Active workspaces"] == ["aa_jenkins", "mm_local", "zz_deploy"]
    assert lane_names(
        build_dashboard(
            rows,
            DashboardFilters(sort="current_host"),
            jenkins_job_url="https://jenkins.example/job/boardwalk/",
            now=now,
        )
    )["Active workspaces"] == ["aa_jenkins", "mm_local", "zz_deploy"]
    assert lane_names(
        build_dashboard(
            rows,
            DashboardFilters(sort="source"),
            jenkins_job_url="https://jenkins.example/job/boardwalk/",
            now=now,
        )
    )["Active workspaces"] == ["zz_deploy", "aa_jenkins", "mm_local"]
    assert lane_names(
        build_dashboard(
            rows,
            DashboardFilters(sort="status", direction="desc"),
            jenkins_job_url="https://jenkins.example/job/boardwalk/",
            now=now,
        )
    )["Active workspaces"] == ["aa_jenkins", "mm_local", "zz_deploy"]
    assert lane_names(
        build_dashboard(
            rows,
            DashboardFilters(sort="updated", direction="desc"),
            jenkins_job_url="https://jenkins.example/job/boardwalk/",
            now=now,
        )
    )["Active workspaces"] == ["zz_deploy", "aa_jenkins", "mm_local"]


def test_source_for_workspace_prefers_jenkins_config_then_deployment_url_then_local():
    jenkins_ws = ws(deployment_number="50321", deployment_url="https://ci.example/build/50321")
    url_ws = ws(deployment_url="https://ci.example/build/standalone")
    local_ws = ws()

    assert source_for_workspace(jenkins_ws, jenkins_job_url="https://jenkins.example/job/boardwalk/") == (
        "jenkins",
        "build 50321",
        "https://jenkins.example/job/boardwalk/50321/",
    )
    assert source_for_workspace(url_ws) == ("deployment", "deployment", "https://ci.example/build/standalone")
    assert source_for_workspace(local_ws) == ("local", "local", "")


def test_query_url_preserves_filters_and_overrides_one_value():
    url = query_url(
        "/workspaces",
        DashboardFilters(group="alpha", search="node", status="running", source="jenkins"),
        group="beta",
    )
    parsed = urlparse(url)

    assert parsed.path == "/workspaces"
    assert parse_qs(parsed.query) == {
        "group": ["beta"],
        "search": ["node"],
        "status": ["running"],
        "source": ["jenkins"],
    }


def test_query_url_omits_default_and_empty_filters():
    assert query_url("/workspaces", DashboardFilters()) == "/workspaces"
    assert query_url("/workspaces", DashboardFilters(group="alpha"), group="All") == "/workspaces"


def test_query_url_preserves_non_default_sort_state():
    url = query_url(
        "/workspaces",
        DashboardFilters(group="alpha", search="node", sort="workspace", direction="desc"),
        group="beta",
    )
    parsed = urlparse(url)

    assert parsed.path == "/workspaces"
    assert parse_qs(parsed.query) == {
        "group": ["beta"],
        "search": ["node"],
        "sort": ["workspace"],
        "direction": ["desc"],
    }


def test_index_template_uses_workspaces_url_for_hx_get():
    loader = Loader(str(Path("src/boardwalkd/templates").resolve()))
    template = loader.load("index.html")
    handler = SimpleNamespace(settings={})

    html = template.generate(
        title="Index",
        edit=False,
        workspaces_url="/workspaces?group=alpha&search=node",
        handler=handler,
        static_url=lambda value: f"/static/{value}",
        server_version=lambda: "test",
        xsrf_form_html=lambda: "",
        _tt_modules=SimpleNamespace(xsrf_form_html=lambda: ""),
    ).decode()

    assert 'class="bw-frame"' in html
    assert 'hx-get="/workspaces?group=alpha&amp;search=node"' in html
    assert 'hx-trigger="load"' in html
    assert "every 8s" not in html


def render_workspace_partial(dashboard, workspaces=None, edit=False):
    loader = Loader(str(Path("src/boardwalkd/templates").resolve()))
    template = loader.load("index_workspace.html")
    return template.generate(
        dashboard=dashboard,
        workspaces=workspaces or {},
        edit=edit,
        auth_prompts=[],
        auth_prompts_by_workspace={},
        orphan_auth_prompts=[],
        jenkins_job_url="https://ci.example/job/boardwalk/",
        action_url=action_url,
        canonical_url=canonical_url,
        partial_url=partial_url,
        query_url=query_url,
        sort_url=sort_url,
        secondsdelta=lambda value: 0,
        sha256=lambda value: hashlib.sha256(value.encode()).hexdigest(),
        sort_events_by_date=lambda events: events,
        squeeze=lambda value: value,
        xsrf_form_html=lambda: "",
    ).decode()


def test_workspace_partial_renders_refreshed_rows_without_progress():
    workspaces = {
        "workspace_alpha": ws(
            group="alpha",
            current_host="node-alpha-a",
            deployment_number="50321",
            events=[WorkspaceEvent(severity="info", message="Locking remote host")],
        )
    }
    dashboard = build_dashboard(
        workspaces,
        DashboardFilters(group="alpha"),
        jenkins_job_url="https://ci.example/job/boardwalk/",
    )

    html = render_workspace_partial(dashboard, workspaces)

    assert 'class="bw-row status-idle"' in html
    assert "workspace_alpha" in html
    assert "node-alpha-a" in html
    assert "Locking remote host" in html
    assert "https://ci.example/job/boardwalk/50321/" in html
    assert "progress" not in html.lower()
    assert "50%" not in html


def test_workspace_partial_renders_lanes_sort_headers_and_advice():
    now = datetime.now(UTC)
    rule = SlackErrorAdviceRule(
        name="Secret store auth expired",
        patterns=["status: 403", "invalid token"],
        message="Abort this CI job and start a fresh Boardwalk job.",
    )
    workspaces = {
        "active_workspace": ws(group="alpha", last_seen=now, current_host="node-active"),
        "auth_expired": ws(
            group="alpha",
            has_mutex=False,
            deployment_number="50321",
            events=[
                WorkspaceEvent(
                    severity="error",
                    message="status: 403 invalid token",
                    create_time=now - timedelta(minutes=5),
                )
            ],
        ),
        "caught_workspace": ws(group="alpha", caught=True, last_seen=now, current_host="node-caught"),
        "inactive_workspace": ws(
            group="alpha",
            has_mutex=False,
            events=[WorkspaceEvent(severity="success", message="done", create_time=now - timedelta(minutes=1))],
        ),
    }
    dashboard = build_dashboard(
        workspaces,
        DashboardFilters(group="alpha"),
        jenkins_job_url="https://ci.example/job/boardwalk/",
        error_advice_rules=[rule],
        now=now,
    )

    html = render_workspace_partial(dashboard, workspaces)

    assert "Active workspaces" in html
    assert "Caught workspaces" in html
    assert "Inactive workspaces" in html
    assert 'class="bw-sort-label">Workspace</span>' in html
    assert 'class="bw-sort-arrow"' in html
    assert 'aria-label="Workspace sorted by default; sort by workspace"' in html
    assert "sort=workspace" in html
    assert "sort=current_host" in html
    assert "sort=source" in html
    assert "sort=status" in html
    assert "sort=updated" in html
    assert "Secret store auth expired" in html
    assert "Abort this CI job and start a fresh Boardwalk job." in html


def test_workspace_partial_places_expand_control_in_workspace_cell_with_stable_key():
    workspaces = {
        "workspace_alpha": ws(
            group="alpha",
            current_host="node-alpha-a",
        )
    }
    dashboard = build_dashboard(workspaces, DashboardFilters(group="alpha"))

    html = render_workspace_partial(dashboard, workspaces)
    workspace_key = hashlib.sha256(b"workspace_alpha").hexdigest()
    row_start = html.index("data-workspace-row")
    name_start = html.index('class="bw-workspace-name"')
    actions_start = html.index('class="bw-actions-cell"')

    assert f'data-workspace-key="{workspace_key}"' in html
    assert f'class="bw-expand" data-row-toggle data-workspace-key="{workspace_key}"' in html
    assert 'class="bw-row-details status-idle"' in html
    assert f'data-workspace-key="{workspace_key}" hidden>' in html
    assert row_start < html.index('class="bw-expand" data-row-toggle') < name_start < actions_start


def test_workspace_partial_catch_release_actions_refresh_current_frame_without_navigation():
    workspaces = {
        "workspace_alpha": ws(
            group="alpha",
            current_host="node-alpha-a",
            caught=False,
            last_seen=datetime.now(UTC),
        )
    }
    dashboard = build_dashboard(workspaces, DashboardFilters(group="alpha", status="running"))

    html = render_workspace_partial(dashboard, workspaces, edit=True)

    assert 'hx-post="/workspace/workspace_alpha/semaphores/caught?group=alpha&amp;status=running&amp;edit=1"' in html
    assert 'hx-target="closest .bw-frame"' in html
    assert 'hx-push-url="false"' in html

    workspaces["workspace_alpha"].semaphores.caught = True
    dashboard = build_dashboard(workspaces, DashboardFilters(group="alpha", status="caught"))

    html = render_workspace_partial(dashboard, workspaces, edit=True)

    assert 'hx-delete="/workspace/workspace_alpha/semaphores/caught?group=alpha&amp;status=caught&amp;edit=1"' in html
    assert 'hx-target="closest .bw-frame"' in html
    assert 'hx-push-url="false"' in html


def test_workspace_partial_polls_current_partial_url_without_pushing_history():
    workspaces = {
        "workspace_alpha": ws(group="alpha", current_host="node-alpha-a"),
    }
    dashboard = build_dashboard(workspaces, DashboardFilters(group="alpha", status="running"))

    html = render_workspace_partial(dashboard, workspaces, edit=True)

    assert 'hx-get="/workspaces?group=alpha&amp;status=running&amp;edit=1"' in html
    assert 'hx-trigger="every 8s"' in html
    assert "push_url=1" not in html.split('hx-trigger="every 8s"', 1)[0]


def test_workspace_partial_uses_canonical_urls_for_htmx_history():
    dashboard = build_dashboard({}, DashboardFilters(group="alpha", search="node", status="running", source="jenkins"))

    html = render_workspace_partial(dashboard, edit=True)

    assert 'href="/?search=node&amp;status=running&amp;source=jenkins&amp;edit=1"' in html
    assert 'hx-get="/workspaces?search=node&amp;status=running&amp;source=jenkins&amp;edit=1&amp;push_url=1"' in html
    assert 'href="/?group=alpha&amp;search=node&amp;status=running&amp;source=jenkins"' in html
    assert 'action="/"' in html
    assert 'hx-get="/workspaces"' in html
    assert 'hx-vals=\'{"push_url":"1"}\'' in html


def test_workspace_partial_renders_remote_cleanup_actions_for_caught_active_workspace():
    workspaces = {
        "workspace_alpha": ws(
            group="alpha",
            current_host="node-alpha-a",
            caught=True,
            last_seen=datetime.now(UTC),
        )
    }
    dashboard = build_dashboard(workspaces, DashboardFilters(group="alpha"))

    html = render_workspace_partial(dashboard, workspaces)

    assert "Clear remote Boardwalk fact file" in html
    assert "Clear remote host mutex" in html


def test_workspace_partial_renders_extra_events_inline_without_more_events_page_link():
    now = datetime.now(UTC)
    workspaces = {
        "workspace_alpha": ws(
            group="alpha",
            current_host="node-alpha-a",
            events=[
                WorkspaceEvent(severity="info", message=f"event {index}", create_time=now - timedelta(seconds=index))
                for index in range(8)
            ],
        )
    }
    dashboard = build_dashboard(workspaces, DashboardFilters(group="alpha"), now=now)

    html = render_workspace_partial(dashboard, workspaces)

    assert "Show 2 more" in html
    assert 'href="/workspace/workspace_alpha/events"' not in html
    assert "data-event-extra" in html


def test_workspace_partial_preserves_filter_state_in_edit_link():
    dashboard = build_dashboard({}, DashboardFilters(group="alpha", search="node", status="running", source="jenkins"))

    html = render_workspace_partial(dashboard)

    assert 'href="/?group=alpha&amp;search=node&amp;status=running&amp;source=jenkins&amp;edit=1"' in html


def test_workspace_partial_renders_edit_delete_actions_with_existing_guards():
    old = datetime.now(UTC) - timedelta(days=8)
    workspaces = {
        "deletable": ws(group="alpha", has_mutex=False, last_seen=old),
        "mutexed": ws(group="alpha", has_mutex=True, last_seen=old),
    }
    dashboard = build_dashboard(workspaces, DashboardFilters(group="alpha"))

    html = render_workspace_partial(dashboard, workspaces, edit=True)

    assert 'hx-post="/workspace/deletable/delete?group=alpha&amp;edit=1"' in html
    assert 'hx-target="closest .bw-frame"' in html
    assert 'hx-delete="/workspace/mutexed/semaphores/has_mutex?group=alpha&amp;edit=1"' in html
    assert "Delete workspace" in html
    assert "Clear workspace mutex" in html


def test_workspace_partial_renders_stale_status_and_filter():
    old = datetime.now(UTC) - timedelta(days=8)
    workspaces = {
        "stale_workspace": ws(group="alpha", last_seen=old),
    }
    dashboard = build_dashboard(workspaces, DashboardFilters(status="stale"), now=datetime.now(UTC))

    html = render_workspace_partial(dashboard, workspaces)

    assert 'class="bw-row status-stale"' in html
    assert '<option value="stale" selected>Stale</option>' in html
    assert "1 stale" in html


def test_is_workspace_active_treats_missing_last_seen_as_inactive(monkeypatch):
    monkeypatch.setattr(
        boardwalkd_server,
        "state",
        SimpleNamespace(workspaces={"missing_last_seen": WorkspaceState(last_seen=None)}),
    )

    assert is_workspace_active("missing_last_seen", now=datetime.now(UTC)) is False


def test_is_workspace_active_uses_supplied_now_for_deterministic_checks(monkeypatch):
    now = datetime(2026, 6, 16, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(
        boardwalkd_server,
        "state",
        SimpleNamespace(
            workspaces={
                "active": WorkspaceState(last_seen=now - timedelta(seconds=9)),
                "inactive": WorkspaceState(last_seen=now - timedelta(seconds=11)),
            }
        ),
    )

    assert is_workspace_active("active", now=now) is True
    assert is_workspace_active("inactive", now=now) is False


def test_base_template_renders_theme_brand_links_and_scripts_without_github_corner():
    loader = Loader(str(Path("src/boardwalkd/templates").resolve()))
    template = loader.load("base.html")
    handler = SimpleNamespace(
        settings={
            "theme_css_url": "/theme-static/boardwalkd-custom.css",
            "theme_logo_url": "/theme-static/custom-logo.svg",
            "theme_logo_alt": "Example",
            "theme_brand_name": "Boardwalk Ops",
        }
    )

    html = template.generate(
        title="Index",
        handler=handler,
        static_url=lambda value: f"/static/{value}",
        server_version=lambda: "test",
        xsrf_form_html=lambda: "",
        _tt_modules=SimpleNamespace(xsrf_form_html=lambda: ""),
    ).decode()

    assert html.index("/static/boardwalkd.css") < html.index("/theme-static/boardwalkd-custom.css")
    assert 'rel="icon"' in html
    assert 'href="/static/favicon.svg"' in html
    assert 'src="/theme-static/custom-logo.svg"' in html
    assert 'alt="Example"' in html
    assert "Boardwalk Ops" in html
    assert 'href="/"' in html
    assert 'href="/admin"' in html
    assert "View source" not in html
    assert "bw-theme-toggle-icon-light" in html
    assert "Switch to dark mode" in html
    assert "/static/boardwalkd.js" in html
    assert "github-corner" not in html
