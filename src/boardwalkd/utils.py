from datetime import UTC, datetime

from boardwalkd import server


def list_active_workspaces(last_seen_seconds: int = 10, _sorted: bool = True) -> list[str]:
    """
    Returns a sorted list[str] of currently active workspaces. Takes
    `last_seen_seconds`, which corresponds to how long ago the worker connected
    to the workspace was last seen. Defaults to 10.
    """
    workspaces: list[str] = []
    for name, workspace in server.state.workspaces.items():
        if (datetime.now(UTC) - workspace.last_seen.replace(tzinfo=UTC)).total_seconds() < last_seen_seconds:  # type: ignore
            workspaces.append(name)
    if _sorted:
        return sorted(workspaces)
    else:
        return workspaces


def is_workspace_active(workspace_name: str, last_seen_seconds: int = 10, now: datetime | None = None) -> bool:
    """Returns True if the workspace has had a recent heartbeat.

    :param workspace_name: The workspace name to check for recent activity.
    :param last_seen_seconds: Seconds since last heartbeat to consider active.
    :param now: Optional datetime used for deterministic tests.
    """
    if ws := server.state.workspaces.get(workspace_name):
        if not ws.last_seen:
            return False
        current_time = (now or datetime.now(UTC)).replace(tzinfo=UTC)
        if (current_time - ws.last_seen.replace(tzinfo=UTC)).total_seconds() < last_seen_seconds:
            return True
    return False


def list_inactive_workspaces(last_seen_seconds: int = 10) -> list[str]:
    """
    Returns a sorted list[str] of inactive workspaces. Takes
    `last_seen_seconds`, which corresponds to the time at which the last
    connected worker was seen before the workspace is considered inactive.
    Defaults to 10.
    """
    return sorted(
        [name for name in server.state.workspaces.keys() if name not in list_active_workspaces(last_seen_seconds)]
    )


def count_of_workspaces_caught() -> int:
    """
    Returns the number of workspaces which are caught
    """
    return len([k for k, v in server.state.workspaces.items() if v.semaphores.caught])
