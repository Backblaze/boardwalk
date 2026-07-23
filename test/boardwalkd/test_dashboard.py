import hashlib
import importlib.resources
import re
from collections import deque
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from types import SimpleNamespace
from typing import cast
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
    UIBaseHandler,
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
    progress_hosts_completed="",
    progress_hosts_total="",
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
            progress_hosts_completed=progress_hosts_completed,
            progress_hosts_total=progress_hosts_total,
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


@pytest.mark.parametrize(
    ("existing_group", "incoming_group", "expected_group"),
    [
        ("", "", ""),
        ("", "ams5", "ams5"),
        ("ams5", "", "ams5"),
        ("ams5", "iad1", "iad1"),
    ],
)
def test_merge_workspace_details_preserves_only_known_group(
    existing_group: str,
    incoming_group: str,
    expected_group: str,
):
    existing = WorkspaceDetails(ui_group=existing_group, workflow="old")
    incoming = WorkspaceDetails(ui_group=incoming_group, workflow="new")

    merged = boardwalkd_server.merge_workspace_details(existing, incoming)

    assert merged.ui_group == expected_group
    assert merged.workflow == "new"
    assert incoming.ui_group == incoming_group


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
    loader = Loader(str(importlib.resources.files("boardwalkd").joinpath("templates")))
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


def render_workspace_partial(dashboard, workspaces=None, edit=False, deletion_issues=()):
    loader = Loader(str(importlib.resources.files("boardwalkd").joinpath("templates")))
    template = loader.load("index_workspace.html")
    return template.generate(
        dashboard=dashboard,
        deletion_issues=deletion_issues,
        workspaces=workspaces or {},
        edit=edit,
        auth_prompts=[],
        auth_prompts_by_workspace={},
        orphan_auth_prompts=[],
        jenkins_job_url="https://ci.example/job/boardwalk/",
        action_url=action_url,
        canonical_url=canonical_url,
        event_time=lambda value: boardwalkd_server.ui_method_event_time(cast(UIBaseHandler, None), value),
        partial_url=partial_url,
        query_url=query_url,
        sort_url=sort_url,
        secondsdelta=lambda value: 0,
        sha256=lambda value: hashlib.sha256(value.encode()).hexdigest(),
        sort_events_by_date=lambda events: events,
        squeeze=lambda value: value,
        xsrf_form_html=lambda: "",
    ).decode()


def test_reserved_all_group_is_only_the_global_tab():
    workspaces = {
        "reserved-group-workspace": ws(group="All", current_host="node-reserved"),
        "alpha-workspace": ws(group="alpha", current_host="node-alpha"),
    }
    dashboard = build_dashboard(workspaces, DashboardFilters())

    assert [(group.label, group.count) for group in dashboard.groups] == [
        ("All", 2),
        ("alpha", 1),
    ]

    html = render_workspace_partial(dashboard, workspaces)
    all_group_key = hashlib.sha256(b"All").hexdigest()
    extracted_id_values = re.findall(r'\bid="([^"]+)"', html)

    assert html.count(f'id="workspace-group-tab-{all_group_key}"') == 1
    assert len(extracted_id_values) == len(set(extracted_id_values))


class RenderedElementCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elements = []

    def handle_starttag(self, tag, attrs):
        self.elements.append({"tag": tag, **dict(attrs)})

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)


def rendered_elements(html):
    parser = RenderedElementCollector()
    parser.feed(html)
    return parser.elements


def test_index_template_initial_frame_uses_morph_swap():
    loader = Loader(str(importlib.resources.files("boardwalkd").joinpath("templates")))
    template = loader.load("index.html")
    html = template.generate(
        title="Index",
        edit=False,
        workspaces_url="/workspaces",
        handler=SimpleNamespace(settings={}),
        static_url=lambda value: f"/static/{value}",
        server_version=lambda: "test",
        xsrf_form_html=lambda: "",
        _tt_modules=SimpleNamespace(xsrf_form_html=lambda: ""),
    ).decode()

    frame = next(element for element in rendered_elements(html) if element.get("class") == "bw-frame")

    assert frame["hx-trigger"] == "load"
    assert frame["hx-swap"] == "morph:innerHTML"


@pytest.mark.parametrize("edit", (False, True))
def test_workspace_partial_frame_actions_use_morph_swap_and_hx_sync(edit):
    now = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)
    workspaces = {
        "caught-active": ws(group="alpha", caught=True, has_mutex=False, last_seen=now),
        "deletable": ws(group="beta", has_mutex=False),
        "mutexed": ws(group="beta", has_mutex=True),
    }
    dashboard = build_dashboard(workspaces, DashboardFilters(), now=now)
    elements = rendered_elements(render_workspace_partial(dashboard, workspaces, edit=edit))
    frame_targets = [element for element in elements if element.get("hx-target") == "closest .bw-frame"]
    polls = [element for element in elements if element.get("hx-trigger") == "every 8s"]
    deliberate_actions = [element for element in frame_targets if element not in polls]

    assert len(polls) == 1
    assert polls[0]["id"] == "workspace-dashboard"
    assert polls[0]["hx-swap"] == "morph:innerHTML"
    assert polls[0]["hx-sync"] == "closest .bw-frame:drop"
    assert deliberate_actions
    assert all(element.get("hx-swap") == "morph:innerHTML" for element in deliberate_actions)
    assert all(element.get("hx-sync") == "closest .bw-frame:replace" for element in deliberate_actions)
    assert not any(element.get("hx-swap") == "innerHTML" for element in frame_targets)

    deliberate_ids = {element.get("id") for element in deliberate_actions}
    deliberate_classes = {
        class_name for element in deliberate_actions for class_name in element.get("class", "").split()
    }
    assert {
        "workspace-search-form",
        "workspace-status-filter-form",
        "workspace-source-filter-form",
        "workspace-edit-toggle",
    }.issubset(deliberate_ids)
    assert {"bw-tab", "bw-sort-arrow", "bw-button-catch", "bw-button-release"}.issubset(deliberate_classes)
    if edit:
        assert "bw-bulk-delete-form" in deliberate_ids
        assert any("/semaphores/has_mutex" in element.get("hx-delete", "") for element in deliberate_actions)
        assert any(
            element.get("hx-post", "").startswith("/workspaces/delete") and element.get("hx-vals")
            for element in deliberate_actions
        )


def test_component_local_and_non_frame_swaps_remain_outside_morph_swap_cutover():
    now = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)
    workspaces = {"caught-active": ws(group="alpha", caught=True, has_mutex=False, last_seen=now)}
    dashboard = build_dashboard(workspaces, DashboardFilters(), now=now)
    dashboard_elements = rendered_elements(render_workspace_partial(dashboard, workspaces))
    cleanup_controls = [
        element for element in dashboard_elements if element.get("hx-target", "").startswith("#remote-")
    ]

    assert len(cleanup_controls) == 2
    assert all(element.get("hx-swap") == "outerHTML" for element in cleanup_controls)
    assert all("hx-sync" not in element for element in cleanup_controls)

    loader = Loader(str(importlib.resources.files("boardwalkd").joinpath("templates")))
    user = SimpleNamespace(email="operator@example.com", enabled=True, roles={"admin"})
    admin_roles = (
        loader.load("admin_user_roles.html")
        .generate(
            user=user,
            valid_user_roles=("admin", "operator"),
            current_user="viewer@example.com",
            owner="owner@example.com",
            sha256=lambda value: hashlib.sha256(value.encode()).hexdigest(),
        )
        .decode()
    )
    admin_enable = (
        loader.load("admin_user_enable.html")
        .generate(
            user=user,
            current_user="viewer@example.com",
            owner="owner@example.com",
            url_escape=lambda value: value,
        )
        .decode()
    )
    workspace_events = (
        loader.load("workspace_events.html")
        .generate(
            title="Events",
            workspace_name="caught-active",
            handler=SimpleNamespace(settings={}),
            static_url=lambda value: f"/static/{value}",
            server_version=lambda: "test",
            xsrf_form_html=lambda: "",
            _tt_modules=SimpleNamespace(xsrf_form_html=lambda: ""),
        )
        .decode()
    )

    role_controls = [
        element
        for element in rendered_elements(admin_roles)
        if element.get("hx-target", "").startswith("#roles-btn-group-")
    ]
    enable_control = next(element for element in rendered_elements(admin_enable) if element.get("hx-delete"))
    event_poll = next(
        element
        for element in rendered_elements(workspace_events)
        if element.get("class") is None and element.get("hx-get", "").endswith("/events/table")
    )

    assert role_controls
    assert all(element.get("hx-swap") == "innerHTML" for element in role_controls)
    assert enable_control["hx-swap"] == "outerHTML"
    assert event_poll["hx-swap"] == "innerHTML"


def test_workspace_partial_dashboard_identity_uses_stable_unique_ids():
    now = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)
    workspaces = {
        "first-workspace": ws(
            group="alpha",
            caught=True,
            has_mutex=False,
            last_seen=now,
        ),
        "second-workspace": ws(
            group="beta",
            has_mutex=False,
        ),
    }
    dashboard = build_dashboard(workspaces, DashboardFilters(), now=now)

    html = render_workspace_partial(dashboard, workspaces, edit=True)
    first_key = hashlib.sha256(b"first-workspace").hexdigest()
    second_key = hashlib.sha256(b"second-workspace").hexdigest()
    group_keys = {label: hashlib.sha256(label.encode()).hexdigest() for label in ("All", "alpha", "beta")}
    extracted_id_values = re.findall(r'\bid="([^"]+)"', html)

    assert 'id="workspace-dashboard"' in html
    assert 'id="workspace-search-form"' in html
    assert 'id="workspace-search"' in html
    assert 'id="workspace-search-submit"' in html
    assert 'id="workspace-status-filter-form"' in html
    assert 'id="workspace-status-filter"' in html
    assert 'id="workspace-source-filter-form"' in html
    assert 'id="workspace-source-filter"' in html
    assert 'id="workspace-edit-toggle"' in html
    assert 'id="workspace-select-visible-done"' in html
    assert 'id="workspace-select-visible-stale"' in html
    assert 'id="workspace-delete-selected"' in html
    for group_key in group_keys.values():
        assert f'id="workspace-group-tab-{group_key}"' in html
    assert {lane.key for lane in dashboard.lanes} == {"caught", "inactive"}
    for lane_key in (lane.key for lane in dashboard.lanes):
        assert f'id="workspace-lane-{lane_key}"' in html
        for sort_key in ("workspace", "updated", "current_host", "source", "status"):
            control_key = hashlib.sha256(f"{lane_key}:{sort_key}".encode()).hexdigest()
            assert f'id="workspace-sort-control-{control_key}"' in html
    assert f'id="workspace-row-{first_key}"' in html
    assert f'id="workspace-toggle-{first_key}"' in html
    assert f'id="workspace-details-{first_key}"' in html
    assert f'id="workspace-delete-{first_key}"' in html
    assert f'aria-controls="workspace-details-{first_key}"' in html
    assert f'id="workspace-row-{second_key}"' in html
    assert f'id="workspace-toggle-{second_key}"' in html
    assert f'id="workspace-details-{second_key}"' in html
    assert f'id="workspace-delete-{second_key}"' in html
    assert all("first-workspace" not in id_value for id_value in extracted_id_values)
    assert all("second-workspace" not in id_value for id_value in extracted_id_values)
    assert len(extracted_id_values) == len(set(extracted_id_values))


def test_workspace_partial_dashboard_identity_keeps_server_truth_authoritative():
    now = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)
    workspace_name = "changing-workspace"
    workspace_key = hashlib.sha256(workspace_name.encode()).hexdigest()
    before_workspaces = {
        workspace_name: ws(
            group="alpha",
            caught=True,
            has_mutex=False,
            last_seen=now,
            events=[WorkspaceEvent(severity="info", message="waiting for release", create_time=now)],
            progress_hosts_completed="1",
            progress_hosts_total="4",
        )
    }
    before_dashboard = build_dashboard(before_workspaces, DashboardFilters(), now=now)

    before_html = render_workspace_partial(before_dashboard, before_workspaces)

    after_workspaces = {
        workspace_name: ws(
            group="beta",
            has_mutex=False,
            events=[WorkspaceEvent(severity="success", message="server says complete", create_time=now)],
            progress_hosts_completed="4",
            progress_hosts_total="4",
        )
    }
    after_dashboard = build_dashboard(after_workspaces, DashboardFilters(), now=now)

    after_html = render_workspace_partial(after_dashboard, after_workspaces)

    stable_id = f'id="workspace-row-{workspace_key}"'
    assert stable_id in before_html
    assert stable_id in after_html
    assert 'class="bw-row status-caught"' in before_html
    assert 'id="workspace-lane-caught"' in before_html
    assert '<progress value="1" max="4"></progress>' in before_html
    assert "waiting for release" in before_html
    assert "Release the workflow catch" in before_html
    assert "Catch the workflow before" not in before_html
    assert 'class="bw-row status-done"' in after_html
    assert 'id="workspace-lane-inactive"' in after_html
    assert '<progress value="4" max="4"></progress>' in after_html
    assert "server says complete" in after_html
    assert "Catch the workflow before" in after_html
    assert "Release the workflow catch" not in after_html


def test_workspace_partial_renders_progress_bar_for_active_ws_when_hosts_not_reported():
    """Deciphering the function, we currently have compatibility with older Boardwalk clients on newer servers,
    so we want an indeterminate progress bar displayed when the worker doesn't report that data."""
    workspaces = {
        "workspace_alpha": ws(
            group="alpha",
            current_host="node-alpha-a",
            deployment_number="50321",
            events=[WorkspaceEvent(severity="info", message="Locking remote host")],
            last_seen=datetime.now(tz=UTC),
        )
    }
    dashboard = build_dashboard(
        workspaces,
        DashboardFilters(group="alpha"),
        jenkins_job_url="https://ci.example/job/boardwalk/",
    )

    html = render_workspace_partial(dashboard, workspaces)

    assert "workspace_alpha" in html
    assert "node-alpha-a" in html
    assert "Locking remote host" in html
    assert "https://ci.example/job/boardwalk/50321/" in html
    assert '<progress value="" max=""></progress>' in html
    assert '<dfn title="the boardwalk worker did not report host completion progress">unknown</dfn>' in html.lower()


def test_workspace_partial_renders_accessible_marked_deletion_issues():
    dashboard = build_dashboard({}, DashboardFilters())

    html = render_workspace_partial(
        dashboard,
        deletion_issues=(
            'Workspace "active" has a connected worker.',
            'Workspace "mutexed" has a server-side mutex.',
        ),
    )

    assert 'role="alert"' in html
    assert 'data-dashboard-error="workspace-deletion"' in html
    assert "data-delete-result" in html
    assert "<li>Workspace &quot;active&quot; has a connected worker.</li>" in html
    assert "<li>Workspace &quot;mutexed&quot; has a server-side mutex.</li>" in html


def workspace_row_markup(html: str, workspace_name: str) -> str:
    workspace_key = hashlib.sha256(workspace_name.encode()).hexdigest()
    key_position = html.index(f'data-workspace-key="{workspace_key}"')
    row_start = html.rfind('<div class="bw-row', 0, key_position)
    row_end = html.index(f'<section id="workspace-details-{workspace_key}"', key_position)
    return html[row_start:row_end]


def checkbox_markup(row_html: str) -> str:
    checkbox_start = row_html.index('<input class="bw-delete-checkbox"')
    checkbox_end = row_html.index(">", checkbox_start) + 1
    return row_html[checkbox_start:checkbox_end]


def test_workspace_partial_renders_bulk_delete_selection_and_row_eligibility_in_edit_mode():
    now = datetime(2026, 7, 14, 21, 40, tzinfo=UTC)
    workspaces = {
        "done_workspace": ws(
            group="alpha",
            has_mutex=False,
            events=[
                WorkspaceEvent(
                    severity="success",
                    message="done",
                    create_time=now - timedelta(minutes=1),
                )
            ],
        ),
        "idle_workspace": ws(group="alpha", has_mutex=False),
        "active_workspace": ws(group="alpha", has_mutex=False, last_seen=now),
        "mutexed_workspace": ws(group="alpha", has_mutex=True),
    }
    dashboard = build_dashboard(workspaces, DashboardFilters(group="alpha"), now=now)

    html = render_workspace_partial(dashboard, workspaces, edit=True)

    assert 'data-select-visible-status="done"' in html
    assert 'data-select-visible-status="stale"' in html
    assert "Select visible done" in html
    assert "Select visible stale" in html
    assert "data-delete-selected" in html
    assert "Delete selected (0)" in html
    assert 'hx-post="/workspaces/delete?group=alpha&amp;edit=1"' in html
    assert "data-bulk-delete-form" in html
    assert "data-delete-result" in html
    assert 'form="bw-bulk-delete-form"' in html
    assert 'aria-live="polite"' in html

    done_row = workspace_row_markup(html, "done_workspace")
    done_checkbox = checkbox_markup(done_row)
    assert 'name="workspace"' in done_checkbox
    assert 'value="done_workspace"' in done_checkbox
    assert 'form="bw-bulk-delete-form"' in done_checkbox
    assert f'data-workspace-key="{hashlib.sha256(b"done_workspace").hexdigest()}"' in done_checkbox
    assert 'data-workspace-status="done"' in done_checkbox
    assert 'aria-label="Select done_workspace for deletion"' in done_checkbox
    assert "disabled" not in done_checkbox

    idle_checkbox = checkbox_markup(workspace_row_markup(html, "idle_workspace"))
    assert 'data-workspace-status="idle"' in idle_checkbox
    assert "disabled" not in idle_checkbox

    active_row = workspace_row_markup(html, "active_workspace")
    assert "disabled" in checkbox_markup(active_row)
    assert "Connected worker prevents deletion" in active_row

    mutexed_row = workspace_row_markup(html, "mutexed_workspace")
    assert "disabled" in checkbox_markup(mutexed_row)
    assert "Server-side mutex prevents deletion" in mutexed_row


def test_workspace_partial_omits_bulk_delete_selection_outside_edit_mode():
    workspaces = {"done_workspace": ws(group="alpha", has_mutex=False)}
    dashboard = build_dashboard(workspaces, DashboardFilters(group="alpha"))

    html = render_workspace_partial(dashboard, workspaces)

    assert "data-bulk-delete-form" not in html
    assert "data-select-visible-status" not in html
    assert "data-delete-selected" not in html
    assert "data-delete-workspace" not in html


def test_workspace_partial_renders_no_progress_bar_for_inactive_ws_when_hosts_not_reported():
    """Deciphering the function, we currently have compatibility with older Boardwalk clients on newer servers,
    so we want an indeterminate progress bar displayed when the worker doesn't report that data."""
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
    assert '<progress value="" max=""></progress>' not in html
    assert '<dfn title="the boardwalk worker did not report host completion progress">unknown</dfn>' in html.lower()


def test_workspace_partial_renders_refreshed_rows_with_progress():
    workspaces = {
        "workspace_alpha": ws(
            group="alpha",
            current_host="node-alpha-a",
            deployment_number="50321",
            events=[WorkspaceEvent(severity="info", message="Locking remote host")],
            progress_hosts_total="42",
            progress_hosts_completed="21",
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
    assert '<progress value="21" max="42"></progress>' in html.lower()
    assert '<dfn title="hosts which have completed their workflow run">21 / 42</dfn>' in html.lower()


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
    now = datetime(2026, 7, 14, 21, 37, 15, tzinfo=UTC)
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
    extra_marker = html.index("data-event-extra")
    extra_start = html.rfind('<div class="bw-event-line', 0, extra_marker)
    extra_end = html.index("</div>", extra_marker)
    extra_event_line = html[extra_start:extra_end]
    expected_time = (
        '<time class="bw-event-time" data-event-time datetime="2026-07-14T21:37:09+00:00" '
        'title="Tuesday, July 14, 2026 at 21:37:09 UTC" '
        'aria-label="Tuesday, July 14, 2026 at 21:37:09 UTC">21:37:09</time>'
    )
    severity = '<span class="bw-event-severity">info</span>'

    assert expected_time in extra_event_line
    assert extra_event_line.index(expected_time) < extra_event_line.index(severity) < extra_event_line.index("event 6")


def test_workspace_partial_renders_event_timestamp_before_severity_and_message():
    create_time = datetime(2026, 7, 14, 21, 37, 9, tzinfo=UTC)
    workspaces = {
        "workspace_alpha": ws(
            group="alpha",
            has_mutex=False,
            events=[WorkspaceEvent(severity="info", message="timestamped event", create_time=create_time)],
        )
    }
    dashboard = build_dashboard(workspaces, DashboardFilters(group="alpha"), now=create_time)

    html = render_workspace_partial(dashboard, workspaces)
    event_start = html.index('<div class="bw-event-line')
    event_end = html.index("</div>", event_start)
    event_line = html[event_start:event_end]
    expected_time = (
        '<time class="bw-event-time" data-event-time datetime="2026-07-14T21:37:09+00:00" '
        'title="Tuesday, July 14, 2026 at 21:37:09 UTC" '
        'aria-label="Tuesday, July 14, 2026 at 21:37:09 UTC">21:37:09</time>'
    )

    assert expected_time in event_line
    severity = '<span class="bw-event-severity">info</span>'
    assert event_line.index(expected_time) < event_line.index(severity) < event_line.index("timestamped event")


def test_workspace_partial_renders_event_timestamp_fallback_for_malformed_time():
    create_time = datetime(2026, 7, 14, 21, 37, 9, tzinfo=UTC)
    workspaces = {
        "workspace_alpha": ws(
            group="alpha",
            has_mutex=False,
            events=[WorkspaceEvent(severity="info", message="placeholder", create_time=create_time)],
        )
    }
    dashboard = build_dashboard(workspaces, DashboardFilters(group="alpha"), now=create_time)
    row = next(row for lane in dashboard.lanes for row in lane.rows if row.name == "workspace_alpha")
    row.events[0] = cast(
        WorkspaceEvent,
        SimpleNamespace(
            severity="warning",
            message="malformed time retained",
            create_time=None,
        ),
    )

    html = render_workspace_partial(dashboard, workspaces)
    event_start = html.index('<div class="bw-event-line')
    event_end = html.index("</div>", event_start)
    event_line = html[event_start:event_end]

    assert '<time class="bw-event-time" data-event-time>—</time>' in event_line
    assert "malformed time retained" in event_line


def test_workspace_partial_renders_event_timestamp_placeholder_when_no_events():
    workspaces = {"workspace_alpha": ws(group="alpha", has_mutex=False)}
    dashboard = build_dashboard(workspaces, DashboardFilters(group="alpha"))

    html = render_workspace_partial(dashboard, workspaces)
    event_start = html.index('<div class="bw-event-line')
    event_end = html.index("</div>", event_start)
    event_line = html[event_start:event_end]

    assert '<time class="bw-event-time" data-event-time>—</time>' in event_line
    assert "No recent events" in event_line


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

    assert r'hx-post="/workspaces/delete' in html
    assert r"""hx-vals='{"workspace": ["deletable"]}'""" in html
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


class FakeDeletionState:
    def __init__(self, workspaces, flush_error: Exception | None = None):
        self.workspaces = workspaces
        self.flush_calls = 0
        self.flush_error = flush_error

    def flush(self):
        self.flush_calls += 1
        if self.flush_error is not None:
            raise self.flush_error


def deletion_workspaces():
    now = datetime.now(UTC)
    return {
        "done": ws(has_mutex=False),
        "other": ws(has_mutex=False),
        "active": ws(has_mutex=False, last_seen=now),
        "mutexed": ws(has_mutex=True),
        "both": ws(has_mutex=True, last_seen=now),
    }


def test_validate_workspace_deletions_accepts_an_eligible_set(monkeypatch):
    fake_state = FakeDeletionState(deletion_workspaces())
    monkeypatch.setattr(boardwalkd_server, "state", fake_state)

    issues = boardwalkd_server.validate_workspace_deletions(["done", "other"])

    assert issues == ()


def test_validate_workspace_deletions_gathers_every_issue_in_request_order(monkeypatch):
    fake_state = FakeDeletionState(deletion_workspaces())
    monkeypatch.setattr(boardwalkd_server, "state", fake_state)

    issues = boardwalkd_server.validate_workspace_deletions(["done", "done", "missing", "active", "mutexed", "both"])

    assert [(issue.workspace, issue.code, issue.message) for issue in issues] == [
        ("done", "duplicate", 'Workspace "done" was requested more than once.'),
        ("missing", "missing", 'Workspace "missing" does not exist.'),
        ("active", "active", 'Workspace "active" has a connected worker.'),
        ("mutexed", "mutex", 'Workspace "mutexed" has a server-side mutex.'),
        ("both", "active", 'Workspace "both" has a connected worker.'),
        ("both", "mutex", 'Workspace "both" has a server-side mutex.'),
    ]


@pytest.mark.parametrize(
    ("workspace_names", "expected_status"),
    [
        ([], 400),
        (["done", "done"], 400),
        (["missing"], 404),
        (["done", "missing"], 404),
        (["active", "missing"], 412),
        (["mutexed"], 412),
    ],
)
def test_workspace_deletion_status_uses_the_most_actionable_blocker(
    monkeypatch,
    workspace_names,
    expected_status,
):
    fake_state = FakeDeletionState(deletion_workspaces())
    monkeypatch.setattr(boardwalkd_server, "state", fake_state)
    issues = boardwalkd_server.validate_workspace_deletions(workspace_names)

    assert boardwalkd_server.workspace_deletion_status(issues) == expected_status


@pytest.mark.parametrize(
    ("workspace_names", "expected_status", "expected_codes"),
    [
        ([], 400, ["empty"]),
        (["done", "done"], 400, ["duplicate"]),
        (["done", "missing"], 404, ["missing"]),
        (["done", "active"], 412, ["active"]),
        (["done", "mutexed"], 412, ["mutex"]),
    ],
)
def test_delete_workspaces_rejects_the_whole_invalid_set_before_mutation(
    monkeypatch,
    workspace_names,
    expected_status,
    expected_codes,
):
    fake_state = FakeDeletionState(deletion_workspaces())
    original_items = tuple(fake_state.workspaces.items())
    monkeypatch.setattr(boardwalkd_server, "state", fake_state)

    with pytest.raises(boardwalkd_server.WorkspaceDeletionRejected) as raised:
        boardwalkd_server.delete_workspaces(workspace_names)

    assert raised.value.status_code == expected_status
    assert [issue.code for issue in raised.value.issues] == expected_codes
    assert tuple(fake_state.workspaces.items()) == original_items
    assert fake_state.flush_calls == 0


def test_delete_workspaces_deletes_the_validated_set_with_one_flush(monkeypatch):
    fake_state = FakeDeletionState(deletion_workspaces())
    monkeypatch.setattr(boardwalkd_server, "state", fake_state)

    boardwalkd_server.delete_workspaces(["done", "other"])

    assert tuple(fake_state.workspaces) == ("active", "mutexed", "both")
    assert fake_state.flush_calls == 1


def test_delete_workspaces_restores_exact_mapping_when_flush_fails(monkeypatch):
    persistence_failure = OSError("disk unavailable")
    fake_state = FakeDeletionState(deletion_workspaces(), flush_error=persistence_failure)
    original_mapping = fake_state.workspaces
    original_items = tuple(original_mapping.items())
    monkeypatch.setattr(boardwalkd_server, "state", fake_state)

    with pytest.raises(boardwalkd_server.WorkspaceDeletionPersistenceError) as raised:
        boardwalkd_server.delete_workspaces(["done", "other"])

    assert fake_state.workspaces is original_mapping
    assert tuple(fake_state.workspaces.items()) == original_items
    assert fake_state.flush_calls == 1
    assert raised.value.deleted == ()
    assert raised.value.failed == ("done", "other")
    assert raised.value.durable_state_uncertain is True
    assert raised.value.__cause__ is persistence_failure
    assert "Durable state needs inspection" in str(raised.value)


def test_base_template_renders_theme_brand_links_and_scripts():
    loader = Loader(str(importlib.resources.files("boardwalkd").joinpath("templates")))
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
        xsrf_form_html=lambda: "xsrf-cookie-seed",
        _tt_modules=SimpleNamespace(xsrf_form_html=lambda: "xsrf-cookie-seed"),
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
    assert 'class="bw-theme-dark"' in html
    assert "Switch to light mode" in html
    assert "/static/boardwalkd.js" in html
    assert "<!-- xsrf-cookie-seed -->" in html
    htmx_xsrf_header = '<body hx-ext="morph" hx-headers=\'js:{"X-XSRFToken": getCookie("_xsrf")}\'>'
    assert htmx_xsrf_header in html
    assert html.index("xsrf-cookie-seed") < html.index(htmx_xsrf_header)
    assert html.index("/static/htmx.min.js") < html.index("/static/idiomorph-ext.min.js")
    assert html.index("/static/idiomorph-ext.min.js") < html.index("/static/boardwalkd.js")
