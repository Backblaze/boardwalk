"""
This file defines models and helpers to support data that's persisted to a local
state and survives service restarts
"""
from collections import deque
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, EmailStr, Extra, validator

from boardwalkd.protocol import WorkspaceDetails, WorkspaceEvent, WorkspaceSemaphores

statefile_dir_path = Path.cwd().joinpath(".boardwalkd")
statefile_path = statefile_dir_path.joinpath("statefile.json")

valid_user_roles = {"default", "admin"}


class StateBaseModel(BaseModel, extra=Extra.forbid):
    """BaseModel for state usage"""


class User(StateBaseModel):
    """Model for user metadata"""

    enabled: bool = True
    email: EmailStr
    roles: set[str] = {"default"}

    @validator("roles")
    def validate_roles(cls, input_roles: set[str]):
        for role in input_roles:
            if role not in valid_user_roles:
                raise ValueError(
                    f"Roles {input_roles} are not valid. Roles may be {valid_user_roles}"
                )
        return input_roles


class WorkspaceState(StateBaseModel):
    """Model for persistent server workspace data"""

    details: WorkspaceDetails = WorkspaceDetails()
    last_seen: datetime | None = None  # When the worker last updated anything
    events: deque[WorkspaceEvent] = deque([], maxlen=64)
    semaphores: WorkspaceSemaphores = WorkspaceSemaphores()


class State(StateBaseModel):
    """Model for persistent server state"""

    workspaces: dict[str, WorkspaceState] = {}
    users: dict[str, User] = {}

    def flush(self):
        """
        Writes state to disk for persistence
        Some items are excluded because they should only be set during runtime
        """
        # Write state to disk.
        statefile_path.write_text(self.json())


def load_state() -> State:
    """If the statefile exists, then returns the State object, else creates
    a statefile and returns an empty State object"""
    try:
        return State().parse_file(statefile_path)
    except FileNotFoundError:
        statefile_dir_path.mkdir(parents=True, exist_ok=True)
        state = State()
        state.flush()
        return state
