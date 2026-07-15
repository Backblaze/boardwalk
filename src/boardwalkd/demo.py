from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from boardwalkd.protocol import WorkspaceDetails, WorkspaceEvent, WorkspaceSemaphores
from boardwalkd.state import State, WorkspaceState


@dataclass(frozen=True)
class DemoWorkspace:
    name: str
    ui_group: str
    host_pattern: str
    current_host: str
    latest_event: str
    caught: bool = False
    build: str = ""
    severity: str = "info"
    has_mutex: bool = False
    stale: bool = False
    extra_events: int = 0
    worker_command: str = "run"
    worker_hostname: str = "demo-worker-01"
    worker_limit: str = ""
    workflow: str = "DemoWorkflow"
    progress_hosts_total: str = "1"
    progress_hosts_completed: str = "0"


DEMO_WORKSPACES = [
    DemoWorkspace(
        name="nodes_alpha_group_upgrade",
        ui_group="alpha",
        host_pattern="nodes_alpha",
        current_host="node-alpha-a",
        latest_event="Waiting for remote catch to release",
        caught=True,
        build="50321",
        extra_events=7,
        workflow="NodeUpgrade",
    ),
    DemoWorkspace(
        name="nodes_beta_group_upgrade",
        ui_group="beta",
        host_pattern="nodes_beta",
        current_host="node-beta-a",
        latest_event="Running main TASK job DrainNode",
        build="50322",
        workflow="NodeUpgrade",
    ),
    DemoWorkspace(
        name="nodes_gamma_group_upgrade",
        ui_group="gamma",
        host_pattern="nodes_gamma",
        current_host="node-gamma-a",
        latest_event="Locking remote host",
        build="50323",
        workflow="NodeUpgrade",
    ),
    DemoWorkspace(
        name="nodes_delta_group_upgrade",
        ui_group="delta",
        host_pattern="nodes_delta",
        current_host="node-delta-a",
        latest_event="Updating remote state",
        workflow="NodeUpgrade",
    ),
    DemoWorkspace(
        name="host_progress_not_available",
        ui_group="host_progress",
        host_pattern="nodes_delta",
        current_host="node-delta-a",
        latest_event="Updating remote state",
        workflow="ProgressNotAvailable",
        progress_hosts_total="",
        progress_hosts_completed="",
    ),
    DemoWorkspace(
        name="host_progress_in_progress",
        ui_group="host_progress",
        host_pattern="nodes_delta",
        current_host="node-delta-a",
        latest_event="Updating remote state",
        workflow="ProgressAvailable",
        progress_hosts_total="73",
        progress_hosts_completed="27",
    ),
    DemoWorkspace(
        name="host_progress_completed",
        ui_group="host_progress",
        host_pattern="nodes_omega",
        current_host="node-omega-a",
        latest_event="Host completed successfully; wrapping up",
        severity="success",
        workflow="NodeUpgrade",
        progress_hosts_total="42",
        progress_hosts_completed="42",
    ),
    DemoWorkspace(
        name="nodes_theta_group_upgrade",
        ui_group="theta",
        host_pattern="nodes_theta",
        current_host="node-theta-a",
        latest_event="Worker details posted",
        workflow="NodeUpgrade",
    ),
    DemoWorkspace(
        name="nodes_multi_group_beta_current",
        ui_group="beta",
        host_pattern="nodes_alpha:nodes_beta:nodes_gamma",
        current_host="node-beta-a",
        latest_event="Derived UI group from current host node-beta-a",
        build="50324",
        workflow="MultiGroupCanary",
    ),
    DemoWorkspace(
        name="nodes_multi_group_gamma_current",
        ui_group="gamma",
        host_pattern="nodes_alpha:nodes_beta:nodes_gamma",
        current_host="node-gamma-a",
        latest_event="Derived UI group from current host node-gamma-a",
        build="50325",
        workflow="MultiGroupCanary",
    ),
    DemoWorkspace(
        name="storage_multi_group_alpha_current",
        ui_group="alpha",
        host_pattern="storage_alpha:storage_beta:storage_gamma",
        current_host="storage-alpha-a",
        latest_event="Storage health check paused for operator catch",
        build="50326",
        workflow="StorageMaintenance",
    ),
    DemoWorkspace(
        name="utility_delta_restart",
        ui_group="delta",
        host_pattern="utility_delta",
        current_host="utility-delta-a",
        latest_event="Restarting boardwalk-safe utility service",
        workflow="UtilityRestart",
    ),
    DemoWorkspace(
        name="workspace_without_group",
        ui_group="",
        host_pattern="manual_debug_host",
        current_host="debug-host-without-ui-group",
        latest_event="Worker details posted without ui_group",
        worker_command="debug",
        worker_hostname="demo-worker-02",
        workflow="ManualDebug",
    ),
    DemoWorkspace(
        name="stale_deletable_workspace",
        ui_group="omega",
        host_pattern="nodes_omega",
        current_host="node-omega-b",
        latest_event="No worker heartbeat for more than a week",
        has_mutex=False,
        stale=True,
        worker_command="run",
        worker_hostname="demo-worker-retired",
        workflow="StaleCleanupDemo",
    ),
    DemoWorkspace(
        name="stale_mutexed_workspace",
        ui_group="theta",
        host_pattern="nodes_theta",
        current_host="node-theta-b",
        latest_event="Server-side workspace mutex remains after stale worker",
        has_mutex=True,
        stale=True,
        worker_command="run",
        worker_hostname="demo-worker-retired",
        workflow="StaleCleanupDemo",
    ),
    DemoWorkspace(
        name="very_very_long_workspace_name_for_fit_testing_and_demo",
        ui_group="alpha",
        host_pattern="nodes_alpha:nodes_beta:nodes_gamma",
        current_host="node-with-a-very-long-current-host-name-for-layout-testing",
        latest_event="Locking remote host",
        build="50327",
        workflow="LongTextFitCheck",
    ),
]


def seed_development_workspaces(state: State) -> bool:
    """Seeds mock dashboard data for local development when state is empty."""
    if state.workspaces:
        return False

    now = datetime.now(UTC)
    demo_connected_until = now + timedelta(hours=1)
    for index, example in enumerate(DEMO_WORKSPACES):
        worker_limit = example.worker_limit or example.current_host or "all"
        last_seen = (
            now - timedelta(days=8, seconds=index) if example.stale else demo_connected_until - timedelta(seconds=index)
        )
        events = [
            WorkspaceEvent(
                severity="info",
                message="Workspace client details posted",
                create_time=now - timedelta(seconds=120 + index),
            ),
            WorkspaceEvent(
                severity="info",
                message="Derived ui_group={} from current_host={}".format(
                    example.ui_group or "Ungrouped",
                    example.current_host or "unknown",
                ),
                create_time=now - timedelta(seconds=60 + index),
            ),
            WorkspaceEvent(
                severity=example.severity,
                message=example.latest_event,
                create_time=now - timedelta(seconds=index),
            ),
        ]
        events.extend(
            WorkspaceEvent(
                severity="info",
                message=f"Demo history line {event_index + 1} for {example.current_host}",
                create_time=now - timedelta(seconds=180 + index + event_index),
            )
            for event_index in range(example.extra_events)
        )
        state.workspaces[example.name] = WorkspaceState(
            details=WorkspaceDetails(
                current_host=example.current_host,
                deployment_number=example.build,
                deployment_user="demo-user",
                host_pattern=example.host_pattern,
                ui_group=example.ui_group,
                worker_command=example.worker_command,
                worker_hostname=example.worker_hostname,
                worker_limit=worker_limit,
                worker_username="demo",
                workflow=example.workflow,
                progress_hosts_completed=example.progress_hosts_completed,
                progress_hosts_total=example.progress_hosts_total,
            ),
            events=deque(events),
            last_seen=last_seen,
            semaphores=WorkspaceSemaphores(caught=example.caught, has_mutex=example.has_mutex),
        )
    return True
