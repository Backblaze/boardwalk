"""
This file defines models and helpers to support data that's persisted to a local
state and survives service restarts
"""

from collections import deque
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, EmailStr, field_validator

from boardwalkd.protocol import WorkspaceDetails, WorkspaceEvent, WorkspaceSemaphores

statefile_dir_path = Path.cwd().joinpath(".boardwalkd")
statefile_path = statefile_dir_path.joinpath("statefile.json")

valid_user_roles = {"default", "admin"}


class StateBaseModel(BaseModel, extra="forbid"):
    """BaseModel for state usage"""


class User(StateBaseModel):
    """Model for user metadata"""

    enabled: bool = True
    email: EmailStr
    roles: set[str] = {"default"}

    @field_validator("roles")
    @classmethod
    def validate_roles(cls, input_roles: set[str]):
        for role in input_roles:
            if role not in valid_user_roles:
                raise ValueError(f"Roles {input_roles} are not valid. Roles may be {valid_user_roles}")
        return input_roles


class WorkspaceState(StateBaseModel):
    """Model for persistent server workspace data"""

    details: WorkspaceDetails = WorkspaceDetails()
    last_seen: datetime | None = None  # When the worker last updated anything
    _max_workspace_events: int = 64
    events: deque[WorkspaceEvent] = deque([], maxlen=_max_workspace_events)
    semaphores: WorkspaceSemaphores = WorkspaceSemaphores()

    @field_validator("events")
    @classmethod
    def validate_events(cls, input_events: deque[WorkspaceEvent]) -> deque[WorkspaceEvent]:
        """
        Pydantic won't persist the maxlen argument for deque when cold loading
        from the statefile. This forces events to always be returned with maxlen
        """
        # TODO: Figure out how to access the value here without using `.default` and needing
        # to ignore type errors; how do you extract an int from a ModelPrivateAttr?
        _max_events = cls._max_workspace_events.default  # type: ignore
        return deque(input_events, maxlen=_max_events)


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
        with open(statefile_path) as fd:
            return State().model_validate_json(fd.read())
    except FileNotFoundError:
        statefile_dir_path.mkdir(parents=True, exist_ok=True)
        state = State()
        state.flush()
        return state
