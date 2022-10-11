from __future__ import annotations

from typing import TYPE_CHECKING

from .manifest import (
    Job as Job,
    path as path,
    Workflow as Workflow,
    Workspace as Workspace,
    WorkspaceConfig as WorkspaceConfig,
)
from .state import RemoteStateModel as RemoteStateModel


if TYPE_CHECKING:
    from boardwalk.ansible import (
        AnsibleTasksType as AnsibleTasksType,
        InventoryHostVars as InventoryHostVars,
    )
