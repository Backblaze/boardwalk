"""
This file holds the state model
"""

from pydantic import BaseModel

from boardwalk.host import Host


class StateBaseModel(BaseModel, extra="forbid"):
    """Base model for local and remote state"""


class LocalState(StateBaseModel):
    """Model for local workspace state"""

    host_pattern: str
    hosts: dict[str, Host] = {}


class RemoteStateWorkflow(StateBaseModel):
    """Workflow data model used for remote state"""

    started: bool = False
    succeeded: bool = False


class RemoteStateWorkspace(StateBaseModel):
    """Workspace data model used for remote state"""

    workflow: RemoteStateWorkflow


class RemoteStateModel(StateBaseModel):
    """Model for remote workspace state save as a fact on hosts"""

    workspaces: dict[str, RemoteStateWorkspace] = {}
