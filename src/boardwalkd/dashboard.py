from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

from boardwalkd.protocol import WorkspaceEvent
from boardwalkd.slack_error_advice import SlackErrorAdviceRule, matching_error_advice
from boardwalkd.state import WorkspaceState

ALL_GROUP = "All"
UNGROUPED = "Ungrouped"
STALE_AFTER = timedelta(hours=24)
DEFAULT_SORT = "default"
DEFAULT_DIRECTION = "asc"
SORT_COLUMNS = {"workspace", "current_host", "source", "status", "updated"}
SORT_DIRECTIONS = {"asc", "desc"}


@dataclass(frozen=True)
class DashboardFilters:
    group: str = ALL_GROUP
    search: str = ""
    status: str = "all"
    source: str = "all"
    sort: str = DEFAULT_SORT
    direction: str = DEFAULT_DIRECTION


@dataclass(frozen=True)
class DashboardGroup:
    label: str
    count: int
    active: bool


@dataclass(frozen=True)
class DashboardAdvice:
    name: str
    message: str


@dataclass(frozen=True)
class DashboardRow:
    name: str
    group: str
    workflow: str
    user: str
    worker: str
    worker_connected: bool
    host_pattern: str
    limit_pattern: str
    current_host: str
    command: str
    source: str
    source_label: str
    source_url: str
    status: str
    latest_event: str
    latest_event_time: datetime
    events: list[WorkspaceEvent]
    advice: list[DashboardAdvice]
    caught: bool
    has_mutex: bool
    stale: bool
    can_request_remote_cleanup: bool
    progress_hosts_completed: str
    progress_hosts_total: str


@dataclass(frozen=True)
class DashboardLane:
    key: str
    label: str
    rows: list[DashboardRow]

    @property
    def count(self) -> int:
        return len(self.rows)


@dataclass(frozen=True)
class Dashboard:
    filters: DashboardFilters
    groups: list[DashboardGroup]
    lanes: list[DashboardLane]
    rows: list[DashboardRow]
    total_count: int
    running_count: int
    caught_count: int
    error_count: int
    done_count: int
    stale_count: int


def group_for_workspace(workspace: WorkspaceState) -> str:
    return workspace.details.ui_group or UNGROUPED


def _event_time(event: WorkspaceEvent) -> datetime:
    if event.create_time is None:
        return datetime.min.replace(tzinfo=UTC)
    return event.create_time.replace(tzinfo=UTC)


def _time_asc_key(value: datetime) -> tuple[int, int, int]:
    return (value.toordinal(), value.hour * 3600 + value.minute * 60 + value.second, value.microsecond)


def _time_desc_key(value: datetime) -> tuple[int, int, int]:
    ordinal, seconds, microseconds = _time_asc_key(value)
    return (-ordinal, -seconds, -microseconds)


def latest_event(workspace: WorkspaceState) -> str:
    if not workspace.events:
        return ""
    event = max(workspace.events, key=_event_time)
    return event.message


def latest_event_time(workspace: WorkspaceState) -> datetime:
    if workspace.events:
        return max(_event_time(event) for event in workspace.events)
    if workspace.last_seen is not None:
        return _normalized_time(workspace.last_seen)
    return datetime.min.replace(tzinfo=UTC)


def _normalized_time(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC)


def worker_connected(workspace: WorkspaceState, now: datetime | None = None) -> bool:
    if workspace.last_seen is None:
        return False
    now = _normalized_time(now or datetime.now(UTC))
    return (now - _normalized_time(workspace.last_seen)).total_seconds() < 10


def worker_stale(workspace: WorkspaceState, now: datetime | None = None) -> bool:
    if workspace.last_seen is None:
        return False
    now = _normalized_time(now or datetime.now(UTC))
    return now - _normalized_time(workspace.last_seen) > STALE_AFTER


def _latest_terminal_event(workspace: WorkspaceState) -> WorkspaceEvent | None:
    terminal_events = [event for event in workspace.events if event.severity in {"error", "success"}]
    if not terminal_events:
        return None
    return max(terminal_events, key=_event_time)


# Status drives the badge/filter value. Lane placement is handled separately in
# _lane_key because a caught workspace with no connected worker is operationally
# different from a caught workspace that can still be released.
def status_for_workspace(workspace: WorkspaceState, now: datetime | None = None) -> str:
    if workspace.semaphores.caught:
        return "caught"
    if worker_connected(workspace, now=now):
        return "running"
    terminal_event = _latest_terminal_event(workspace)
    if terminal_event is not None:
        if terminal_event.severity == "error":
            return "error"
        if terminal_event.severity == "success":
            return "done"
    if worker_stale(workspace, now=now):
        return "stale"
    return "idle"


def source_for_workspace(workspace: WorkspaceState, jenkins_job_url: str = "") -> tuple[str, str, str]:
    build = workspace.details.deployment_number
    deployment_url = workspace.details.deployment_url
    if build and jenkins_job_url:
        return ("jenkins", f"build {build}", f"{jenkins_job_url.rstrip('/')}/{build}/")
    if deployment_url:
        return ("deployment", f"build {build}" if build else "deployment", deployment_url)
    return ("local", "local", "")


def row_for_workspace(
    name: str,
    workspace: WorkspaceState,
    jenkins_job_url: str = "",
    error_advice_rules: Sequence[SlackErrorAdviceRule] = (),
    now: datetime | None = None,
) -> DashboardRow:
    source, source_label, source_url = source_for_workspace(workspace, jenkins_job_url=jenkins_job_url)
    connected = worker_connected(workspace, now=now)
    stale = worker_stale(workspace, now=now)
    status = status_for_workspace(workspace, now=now)
    terminal_event = _latest_terminal_event(workspace)
    advice = [
        DashboardAdvice(name=rule.name, message=rule.message)
        for rule in (
            matching_error_advice(terminal_event, list(error_advice_rules))
            if status == "error" and terminal_event
            else []
        )
    ]
    return DashboardRow(
        name=name,
        group=group_for_workspace(workspace),
        workflow=workspace.details.workflow,
        user=workspace.details.deployment_user or workspace.details.worker_username,
        worker=f"{workspace.details.worker_username}@{workspace.details.worker_hostname}",
        worker_connected=connected,
        host_pattern=workspace.details.host_pattern,
        limit_pattern=workspace.details.worker_limit or "all",
        current_host=workspace.details.current_host,
        command=workspace.details.worker_command,
        source=source,
        source_label=source_label,
        source_url=source_url,
        status=status,
        latest_event=latest_event(workspace),
        latest_event_time=latest_event_time(workspace),
        events=sorted(workspace.events, key=_event_time, reverse=True),
        advice=advice,
        caught=workspace.semaphores.caught,
        has_mutex=workspace.semaphores.has_mutex,
        stale=stale,
        can_request_remote_cleanup=workspace.semaphores.caught and connected,
        progress_hosts_completed=workspace.details.progress_hosts_completed,
        progress_hosts_total=workspace.details.progress_hosts_total,
    )


def _group_sort_key(group: str) -> tuple[int, str]:
    if group == UNGROUPED:
        return (1, group.casefold())
    return (0, group.casefold())


def group_counts(rows: Sequence[DashboardRow]) -> dict[str, int]:
    counts = {ALL_GROUP: len(rows)}
    for row in rows:
        if row.group == ALL_GROUP:
            continue
        counts[row.group] = counts.get(row.group, 0) + 1
    return counts


def _matches_filters(row: DashboardRow, filters: DashboardFilters, *, include_group: bool = True) -> bool:
    if include_group and filters.group and filters.group != ALL_GROUP and row.group != filters.group:
        return False
    if filters.status and filters.status != "all" and row.status != filters.status:
        return False
    if filters.source and filters.source != "all" and row.source != filters.source:
        return False
    if filters.search:
        query = filters.search.casefold()
        searchable = " ".join(
            [
                row.name,
                row.current_host,
                row.limit_pattern,
                row.user,
                row.worker,
                row.source,
                row.source_label,
                row.source_url,
                " ".join(advice.name for advice in row.advice),
                " ".join(advice.message for advice in row.advice),
            ]
        ).casefold()
        if query not in searchable:
            return False
    return True


def _normalized_sort(sort: str) -> str:
    return sort if sort in SORT_COLUMNS else DEFAULT_SORT


def _normalized_direction(direction: str) -> str:
    return direction if direction in SORT_DIRECTIONS else DEFAULT_DIRECTION


def _normalized_filters(filters: DashboardFilters) -> DashboardFilters:
    return DashboardFilters(
        group=filters.group,
        search=filters.search,
        status=filters.status,
        source=filters.source,
        sort=_normalized_sort(filters.sort),
        direction=_normalized_direction(filters.direction),
    )


ACTIVE_STATUS_PRIORITY = {
    "running": 0,
}

CAUGHT_STATUS_PRIORITY = {
    "caught": 0,
}

INACTIVE_STATUS_PRIORITY = {
    "error": 0,
    "caught": 1,
    "stale": 3,
    "idle": 4,
    "done": 5,
}

COLUMN_STATUS_PRIORITY = {
    "caught": 0,
    "running": 1,
    "error": 2,
    "done": 3,
    "idle": 4,
    "stale": 5,
}


# Lanes describe what the operator can act on now. A caught workspace only stays
# in the caught lane while a worker heartbeat is active; once disconnected, it is
# inactive even though its status badge remains caught.
def _lane_key(row: DashboardRow) -> str:
    if row.worker_connected and row.caught:
        return "caught"
    if row.worker_connected:
        return "active"
    return "inactive"


# The default ordering is tuned for live operations: active work shows the most
# recent movement first, caught work shows the longest-waiting pauses first, and
# inactive work puts likely follow-up items ahead of stale/done history.
def _default_lane_sort_key(lane_key: str):
    def active_key(row: DashboardRow) -> tuple[int, tuple[int, int, int], str]:
        return (ACTIVE_STATUS_PRIORITY.get(row.status, 99), _time_desc_key(row.latest_event_time), row.name.casefold())

    def caught_key(row: DashboardRow) -> tuple[int, tuple[int, int, int], str]:
        return (CAUGHT_STATUS_PRIORITY.get(row.status, 99), _time_asc_key(row.latest_event_time), row.name.casefold())

    def inactive_key(row: DashboardRow) -> tuple[int, tuple[int, int, int], str]:
        status_priority = 0 if row.advice else 2 if row.has_mutex else INACTIVE_STATUS_PRIORITY.get(row.status, 99)
        return (status_priority, _time_asc_key(row.latest_event_time), row.name.casefold())

    if lane_key == "active":
        return active_key
    if lane_key == "caught":
        return caught_key
    return inactive_key


def _column_sort_key(sort: str):
    if sort == "workspace":
        return lambda row: row.name.casefold()
    if sort == "current_host":
        return lambda row: (row.current_host or "unknown").casefold()
    if sort == "source":
        return lambda row: (row.source, row.source_label.casefold(), row.name.casefold())
    if sort == "status":
        return lambda row: COLUMN_STATUS_PRIORITY.get(row.status, 99)
    if sort == "updated":
        return lambda row: _time_asc_key(row.latest_event_time)
    return lambda row: row.name.casefold()


def _sort_lane_rows(rows: list[DashboardRow], filters: DashboardFilters, lane_key: str) -> list[DashboardRow]:
    sorted_rows = list(rows)
    if filters.sort == DEFAULT_SORT:
        sorted_rows.sort(key=_default_lane_sort_key(lane_key))
        return sorted_rows

    sorted_rows.sort(key=lambda row: row.name.casefold())
    sorted_rows.sort(key=_column_sort_key(filters.sort), reverse=filters.direction == "desc")
    return sorted_rows


def _build_lanes(rows: Sequence[DashboardRow], filters: DashboardFilters) -> list[DashboardLane]:
    grouped_rows = {"active": [], "caught": [], "inactive": []}
    for row in rows:
        grouped_rows[_lane_key(row)].append(row)

    lanes = [
        ("active", "Active workspaces"),
        ("caught", "Caught workspaces"),
        ("inactive", "Inactive workspaces"),
    ]
    return [
        DashboardLane(key=key, label=label, rows=_sort_lane_rows(grouped_rows[key], filters, key))
        for key, label in lanes
        if grouped_rows[key]
    ]


def build_dashboard(
    workspaces: Mapping[str, WorkspaceState],
    filters: DashboardFilters,
    jenkins_job_url: str = "",
    error_advice_rules: Sequence[SlackErrorAdviceRule] = (),
    now: datetime | None = None,
) -> Dashboard:
    filters = _normalized_filters(filters)
    all_rows = [
        row_for_workspace(
            name,
            workspace,
            jenkins_job_url=jenkins_job_url,
            error_advice_rules=error_advice_rules,
            now=now,
        )
        for name, workspace in workspaces.items()
    ]
    count_rows = [row for row in all_rows if _matches_filters(row, filters, include_group=False)]
    counts = group_counts(count_rows)
    group_labels = sorted({row.group for row in all_rows if row.group != ALL_GROUP}, key=_group_sort_key)
    groups = [
        DashboardGroup(label=ALL_GROUP, count=counts[ALL_GROUP], active=filters.group in {"", ALL_GROUP}),
        *[
            DashboardGroup(label=label, count=counts.get(label, 0), active=filters.group == label)
            for label in group_labels
        ],
    ]
    visible_rows = [row for row in all_rows if _matches_filters(row, filters)]
    lanes = _build_lanes(visible_rows, filters)
    rows = [row for lane in lanes for row in lane.rows]
    return Dashboard(
        filters=filters,
        groups=groups,
        lanes=lanes,
        rows=rows,
        total_count=len(rows),
        running_count=sum(1 for row in rows if row.status == "running"),
        caught_count=sum(1 for row in rows if row.status == "caught"),
        error_count=sum(1 for row in rows if row.status == "error"),
        done_count=sum(1 for row in rows if row.status == "done"),
        stale_count=sum(1 for row in rows if row.status == "stale"),
    )


def query_url(path: str, filters: DashboardFilters, **overrides: str) -> str:
    filters = _normalized_filters(filters)
    values = {
        "group": filters.group,
        "search": filters.search,
        "status": filters.status,
        "source": filters.source,
        "sort": filters.sort,
        "direction": filters.direction,
    }
    values.update(overrides)
    sort = _normalized_sort(values.get("sort", DEFAULT_SORT))
    direction = _normalized_direction(values.get("direction", DEFAULT_DIRECTION))
    values["sort"] = sort
    values["direction"] = direction
    query = {
        key: value
        for key, value in values.items()
        if value
        and value != ALL_GROUP
        and value != "all"
        and not (key == "sort" and value == DEFAULT_SORT)
        and not (key == "direction" and (sort == DEFAULT_SORT or direction == DEFAULT_DIRECTION))
    }
    return f"{path}?{urlencode(query)}" if query else path


def next_sort_direction(filters: DashboardFilters, column: str) -> str:
    filters = _normalized_filters(filters)
    if filters.sort == column and filters.direction == DEFAULT_DIRECTION:
        return "desc"
    return DEFAULT_DIRECTION


def sort_url(path: str, filters: DashboardFilters, column: str, edit: bool = False, **overrides: str) -> str:
    if edit:
        overrides.setdefault("edit", "1")
    overrides["sort"] = column
    overrides["direction"] = next_sort_direction(filters, column)
    return query_url(path, filters, **overrides)


def canonical_url(filters: DashboardFilters, edit: bool = False, **overrides: str) -> str:
    if edit:
        overrides.setdefault("edit", "1")
    return query_url("/", filters, **overrides)


def action_url(path: str, filters: DashboardFilters, edit: bool = False, **overrides: str) -> str:
    if edit:
        overrides.setdefault("edit", "1")
    return query_url(path, filters, **overrides)


def partial_url(
    filters: DashboardFilters,
    edit: bool = False,
    push_url: bool = False,
    **overrides: str,
) -> str:
    if edit:
        overrides.setdefault("edit", "1")
    if push_url:
        overrides.setdefault("push_url", "1")
    return query_url("/workspaces", filters, **overrides)
