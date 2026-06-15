from __future__ import annotations

import json
import re
from collections import deque
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from boardwalkd.protocol import WorkspaceDetails, WorkspaceEvent, WorkspaceSemaphores
from boardwalkd.state import State, WorkspaceState

SNAPSHOT_FORMAT = "boardwalkd-status-snapshot-v1"
GROUP_LABEL_PATTERN = re.compile(r"^[a-z][a-z0-9-]*_(?P<group>[a-z][a-z0-9-]*)$")


def _normalized_now(now: datetime | None = None) -> datetime:
    return (now or datetime.now(UTC)).replace(tzinfo=UTC)


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)).replace(tzinfo=UTC)
    except ValueError:
        return None


def _safe_label(value: str, fallback: str = "ungrouped") -> str:
    label = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip()).strip("_").lower()
    return label or fallback


def _group_from_pattern_part(value: str) -> str:
    match = GROUP_LABEL_PATTERN.match(value.lower().strip())
    return match.group("group") if match else ""


def _group_labels(value: Any) -> list[str]:
    if not value:
        return []
    labels = []
    for part in str(value).split(":"):
        label = _group_from_pattern_part(part)
        if label and label not in labels:
            labels.append(label)
    return labels


def load_inventory_context(path: str | Path | None) -> Mapping[str, Any] | None:
    if path is None:
        return None
    return json.loads(Path(path).read_text())


def _inventory_parents(inventory: Mapping[str, Any]) -> dict[str, set[str]]:
    parents: dict[str, set[str]] = {}
    for group, body in inventory.items():
        if group == "_meta" or not isinstance(body, Mapping):
            continue
        for child in body.get("children", []) or []:
            parents.setdefault(str(child), set()).add(str(group))
    return parents


def _inventory_labels_for_group(
    group: str,
    parents: Mapping[str, set[str]],
    seen: set[str] | None = None,
) -> set[str]:
    match = GROUP_LABEL_PATTERN.match(group)
    if match:
        return {match.group("group")}
    seen = seen or set()
    if group in seen:
        return set()
    seen.add(group)
    labels: set[str] = set()
    for parent in parents.get(group, set()):
        labels.update(_inventory_labels_for_group(parent, parents, seen))
    return labels


def _inventory_labels_for_pattern(pattern: Any, inventory: Mapping[str, Any] | None) -> set[str]:
    if not pattern or inventory is None:
        return set()
    parents = _inventory_parents(inventory)
    labels: set[str] = set()
    for raw_part in str(pattern).split(":"):
        part = raw_part.strip()
        if not part or part.startswith("!") or part.startswith("&"):
            continue
        labels.update(_inventory_labels_for_group(part, parents))
    return labels


def _derived_group(details: Mapping[str, Any], inventory: Mapping[str, Any] | None = None) -> str:
    ui_group = str(details.get("ui_group") or "")
    if ui_group:
        return ui_group
    current_host_group = _group_from_pattern_part(str(details.get("current_host") or ""))
    if current_host_group:
        return current_host_group
    host_pattern_groups = _group_labels(details.get("host_pattern"))
    if len(host_pattern_groups) == 1:
        return host_pattern_groups[0]
    if len(host_pattern_groups) > 1:
        return "Multi-group"
    inventory_groups = _inventory_labels_for_pattern(details.get("host_pattern"), inventory)
    if len(inventory_groups) == 1:
        return next(iter(inventory_groups))
    if len(inventory_groups) > 1:
        return "Multi-group"
    return ""


def _redacted_pattern(value: Any, group: str, index: int) -> str:
    if not value:
        return ""
    fallback = _safe_label(group)
    parts = str(value).split(":")
    labels = [_safe_label(_group_from_pattern_part(part) or group, fallback=fallback) for part in parts]
    return ":".join(f"pattern-{label}-{index:03d}" for label in labels)


def _redacted_details(details: Mapping[str, Any], index: int, inventory: Mapping[str, Any] | None) -> WorkspaceDetails:
    group = _derived_group(details, inventory=inventory)
    group_label = _safe_label(group)
    current_host = str(details.get("current_host") or "")
    redacted_current_host = f"snapshot-host-{group_label}-{index:03d}" if current_host else ""
    deployment_number = str(details.get("deployment_number") or "")
    deployment_url = str(details.get("deployment_url") or "")
    return WorkspaceDetails(
        current_host=redacted_current_host,
        deployment_name=f"snapshot-deployment-{index:03d}" if details.get("deployment_name") else "",
        deployment_number=f"snapshot-build-{index:03d}" if deployment_number else "",
        deployment_tag=f"snapshot-tag-{index:03d}" if details.get("deployment_tag") else "",
        deployment_url=f"https://snapshot.invalid/deployment/{index:03d}/" if deployment_url else "",
        deployment_user=f"snapshot-user-{index:03d}" if details.get("deployment_user") else "",
        deployment_user_email=(
            f"snapshot-user-{index:03d}@example.invalid" if details.get("deployment_user_email") else ""
        ),
        deployment_user_id=f"snapshot-user-id-{index:03d}" if details.get("deployment_user_id") else "",
        host_pattern=_redacted_pattern(details.get("host_pattern"), group, index),
        ui_group=group,
        workflow=f"SnapshotWorkflow{index:03d}" if details.get("workflow") else "",
        worker_command="snapshot run" if details.get("worker_command") else "",
        worker_hostname=f"snapshot-worker-{group_label}-{index:03d}" if details.get("worker_hostname") else "",
        worker_limit=(
            redacted_current_host
            if details.get("worker_limit") and details.get("worker_limit") == details.get("current_host")
            else _redacted_pattern(details.get("worker_limit"), group, index)
        ),
        worker_username="snapshot-worker" if details.get("worker_username") else "",
    )


def _preserved_details(details: Mapping[str, Any], inventory: Mapping[str, Any] | None) -> WorkspaceDetails:
    return WorkspaceDetails(
        current_host=str(details.get("current_host") or ""),
        deployment_name=str(details.get("deployment_name") or ""),
        deployment_number=str(details.get("deployment_number") or ""),
        deployment_tag=str(details.get("deployment_tag") or ""),
        deployment_url=str(details.get("deployment_url") or ""),
        deployment_user=str(details.get("deployment_user") or ""),
        deployment_user_email=str(details.get("deployment_user_email") or ""),
        deployment_user_id=str(details.get("deployment_user_id") or ""),
        host_pattern=str(details.get("host_pattern") or ""),
        ui_group=_derived_group(details, inventory=inventory),
        workflow=str(details.get("workflow") or ""),
        worker_command=str(details.get("worker_command") or ""),
        worker_hostname=str(details.get("worker_hostname") or ""),
        worker_limit=str(details.get("worker_limit") or ""),
        worker_username=str(details.get("worker_username") or ""),
    )


def _sanitized_semaphores(value: Mapping[str, Any]) -> WorkspaceSemaphores:
    return WorkspaceSemaphores(
        caught=bool(value.get("caught", False)),
        clear_remote_mutex_requested=bool(value.get("clear_remote_mutex_requested", False)),
        clear_remote_state_requested=bool(value.get("clear_remote_state_requested", False)),
        has_mutex=bool(value.get("has_mutex", False)),
    )


def sanitize_status_snapshot(
    snapshot: Mapping[str, Any],
    now: datetime | None = None,
    preserve_identifiers: bool = False,
    inventory: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a replayable snapshot converted from /api/workspaces/status JSON."""
    captured_at = _normalized_now(now)
    sanitized: dict[str, Any] = {
        "snapshot_format": SNAPSHOT_FORMAT,
        "captured_at": captured_at.isoformat(),
        "workspaces": [],
    }
    for index, entry in enumerate(snapshot.get("workspaces", []), start=1):
        details = entry.get("details") or {}
        semaphores = entry.get("semaphores") or {}
        group_label = _safe_label(_derived_group(details, inventory=inventory))
        workspace_details = (
            _preserved_details(details, inventory=inventory)
            if preserve_identifiers
            else _redacted_details(details, index, inventory=inventory)
        )
        source_last_seen = _parse_time(entry.get("last_seen"))
        last_seen_age_seconds = None
        if source_last_seen is not None:
            last_seen_age_seconds = max(0, int((captured_at - source_last_seen).total_seconds()))
        workspace_name = (
            str(entry.get("name") or f"snapshot_{group_label}_{index:03d}")
            if preserve_identifiers
            else f"snapshot_{group_label}_{index:03d}"
        )
        sanitized["workspaces"].append(
            {
                "name": workspace_name,
                "details": workspace_details.model_dump(),
                "semaphores": _sanitized_semaphores(semaphores).model_dump(),
                "worker_connected": bool(details.get("worker_connected", False)),
                "last_seen_age_seconds": last_seen_age_seconds,
            }
        )
    return sanitized


def load_status_snapshot(path: str | Path, now: datetime | None = None) -> dict[str, Any]:
    data = json.loads(Path(path).read_text())
    if data.get("snapshot_format") == SNAPSHOT_FORMAT:
        return data
    return sanitize_status_snapshot(data, now=now)


def _snapshot_last_seen(entry: Mapping[str, Any], index: int, now: datetime) -> datetime | None:
    if entry.get("worker_connected"):
        return now + timedelta(hours=1) - timedelta(seconds=index)
    age = entry.get("last_seen_age_seconds")
    if age is None:
        return None
    return now - timedelta(seconds=int(age))


def seed_snapshot_workspaces(state: State, path: str | Path, now: datetime | None = None) -> bool:
    """Seed state from a sanitized status snapshot without overwriting existing workspaces."""
    if state.workspaces:
        return False

    replay_now = _normalized_now(now)
    snapshot = load_status_snapshot(path, now=replay_now)
    for index, entry in enumerate(snapshot.get("workspaces", []), start=1):
        name = str(entry["name"])
        details = WorkspaceDetails.model_validate(entry.get("details") or {})
        semaphores = WorkspaceSemaphores.model_validate(entry.get("semaphores") or {})
        event = WorkspaceEvent(
            severity="info",
            message=(
                "Sanitized production status snapshot replay: "
                f"ui_group={details.ui_group or 'Ungrouped'} "
                f"current_host={details.current_host or 'unknown'}"
            ),
            create_time=replay_now - timedelta(seconds=index),
        )
        state.workspaces[name] = WorkspaceState(
            details=details,
            events=deque([event]),
            last_seen=_snapshot_last_seen(entry, index, replay_now),
            semaphores=semaphores,
        )
    return True
