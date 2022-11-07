"""
This file has all of the classes and functions that are used in a
Boardwalkfile.py
"""
from __future__ import annotations

import os
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING

from click import ClickException

from boardwalk.state import LocalState

if TYPE_CHECKING:
    from typing import Any, Callable

    from boardwalk.ansible import AnsibleFacts, AnsibleTasksType, InventoryHostVars

workspaces_dir = Path.cwd().joinpath(".boardwalk/workspaces")
active_workspace_file = workspaces_dir.joinpath("active_workspace.txt")


class DuplicateManifestClass(Exception):
    """More than one class with same name is defined in the manifest"""


class ManifestNotFound(Exception):
    """No Boardwalkfile.py was found"""


class NoActiveWorkspace(Exception):
    """There is no workspace active"""

    message = (
        "No workspace selected."
        " Use `boardwalk workspace list` to list workspaces"
        " and `boardwalk workspace use` to select one"
    )


class WorkspaceNotFound(Exception):
    """The workspace does not exist"""


def get_ws() -> Workspace:
    """Imports the Boardwalkfile.py and returns the active Workspace"""

    # Try to import the Boardwalkfile.py
    try:
        sys.path.append(str(Path.cwd()))
        import Boardwalkfile  # pyright: reportMissingImports=false,reportUnknownVariableType=false,reportUnusedImport=false

        sys.path.pop()
    except ModuleNotFoundError:
        raise ManifestNotFound

    # Check if there are duplicate class names
    class_list = [Job, Workspace, Workflow, WorkspaceConfig]
    for item in class_list:
        subclasses: list[str] = []
        for subclass in item.__subclasses__():
            subclasses.append(subclass.__qualname__)
        if len(subclasses) != len(set(subclasses)):
            raise DuplicateManifestClass(
                "Duplicate class names defined in Boardwalkfile.py"
            )

    # Get the active Workspace name, if there is one
    # If the BOARDWALK_WORKSPACE var is set, try to use that Workspace name
    if "BOARDWALK_WORKSPACE" in os.environ:
        active_workspace_name = os.getenv("BOARDWALK_WORKSPACE")
    else:
        # If a workspace is already active, use that one, if it's in the Boardwalkfile
        try:
            active_workspace_name = active_workspace_file.read_text().rstrip()
        except FileNotFoundError:
            raise NoActiveWorkspace

    # If somehow the active workspace name did not get set, we panic
    if not active_workspace_name:
        raise Exception("active_workspace_name is not set but it should have been")

    # Ensure the active Workspace name actually exists.
    if Workspace.exists(active_workspace_name):
        return Workspace.fetch_subclass(active_workspace_name)()
    else:
        raise WorkspaceNotFound(f'Workspace "{active_workspace_name}" does not exist.')


def get_boardwalkd_url() -> str:
    try:
        sys.path.append(str(Path.cwd()))
        from Boardwalkfile import boardwalkd_url

        sys.path.pop()
    except ModuleNotFoundError:
        raise ManifestNotFound
    except ImportError:
        return None
    return boardwalkd_url


class Job:
    """Defines a single Job as methods"""

    def __init__(self, options: dict[str, Any] = dict()):
        self.name = self.__class__.__name__
        self._check_options(options)
        self.options = options
        """Optional dict of options that can be leveraged inside the class"""

    def required_options(self) -> tuple[str]:
        """Optional user method. Defines any required Job input options"""
        return tuple()

    def preconditions(
        self, facts: AnsibleFacts, inventory_vars: InventoryHostVars
    ) -> bool:
        """Optional user method. Return True if preconditions are met, else return False"""
        return True

    def tasks(self) -> AnsibleTasksType:
        """Optional user method. Return list of Ansible tasks to run. If an
        empty list is returned, then the workflow doesn't connect to a host,
        however, any code in this method still runs"""
        return []

    def _required_options(self) -> tuple[str]:
        """
        Internal helper method. Always returns self.required_options() as a
        tuple, even if the user returns as single string
        """
        req_options = self.required_options()
        if isinstance(self.required_options(), str):
            req_options: tuple[str] = (
                req_options,  # pyright: reportGeneralTypeIssues=false
            )
        return req_options

    def _check_options(self, options: dict[str, Any]):
        """Internal method. Checks required options have been set. Raises a ValueError if not"""
        missing_options: list[str] = []
        for opt in self._required_options():
            if opt not in options:
                missing_options.append(opt)
        if len(missing_options) > 0:
            raise ValueError(f"Required options missing: {', '.join(missing_options)}")


class Workflow(ABC):
    """Defines a workflow of Jobs"""

    def __init__(self):
        # If user-provided Jobs as a single Job, convert to tuple
        workflow_jobs = self.jobs()
        if isinstance(workflow_jobs, Job):
            workflow_jobs = (workflow_jobs,)
        workflow_exit_jobs = self.exit_jobs()
        if isinstance(workflow_exit_jobs, Job):
            workflow_exit_jobs = (workflow_exit_jobs,)
        # self._jobs is the list of initialized Jobs.
        self.i_jobs = workflow_jobs
        # self._exit_jobs is the list of initialized Jobs.
        self.i_exit_jobs = workflow_exit_jobs

    @abstractmethod
    def jobs(self) -> Job | tuple[Job, ...]:
        """Required user method. Defines the Jobs in a workflow. Order matters"""
        raise NotImplementedError

    def exit_jobs(self) -> Job | tuple[Job, ...]:
        """
        Optional user method. Defines Workflow Jobs that we will always try
        to run, even on failure. Order matters. exit_jobs run after regular Jobs
        """
        return ()


class WorkspaceConfig:
    """
    Configuration block for workspaces

    :param default_sort_order: The default order hosts will be walked through
    (by hostname). Valid sort orders are specified in the valid_sort_orders
    attribute
    :param host_pattern: The Ansible host pattern the workspace targets. If this
    changes after initialization, the workspace needs to be re-initialized
    :param require_limit: `check` and `run` subcommands will require the --limit
    option to be passed. This is useful for workspaces configured with a broad
    host pattern but workflows should be intentionally down-scoped to a specific
    pattern
    :param workflow: The workflow the workspace uses
    """

    valid_sort_orders = ["ascending", "descending", "shuffle"]

    def __init__(
        self,
        host_pattern: str,
        workflow: Workflow,
        default_sort_order: str = "shuffle",
        require_limit: bool = False,
    ):
        self.default_sort_order = default_sort_order
        self.host_pattern = host_pattern
        self.require_limit = require_limit
        self.workflow = workflow

    @property
    def default_sort_order(self) -> str:
        return self._default_sort_order

    @default_sort_order.setter
    def default_sort_order(self, value: str):
        self._is_valid_sort_order(value)
        self._default_sort_order = value

    def _is_valid_sort_order(self, value: str):
        """Checks if a given sort order is valid. Raises a ValueError if not"""
        if value not in self.valid_sort_orders:
            raise ValueError(
                f"Valid default_sort_order values are: {', '.join(self.valid_sort_orders)}"
            )


class Workspace(ABC):
    """
    Handles everything to do with the active workspace directory. "Workspaces"
    are used to hold configuration and temporary information. This is done so
    different upgrade projects are possible to do in parallel. This class
    implements the singleton pattern, because the same Workspace may be
    instantiated in many areas
    """

    _initialized: bool = False
    _instance: Workspace | None = None

    def __new__(cls):
        # Singleton. Only create a new instance if one doesn't already exist
        if cls._instance is None:
            cls._instance = super(Workspace, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            # Set the workspace name and set it as active by writing it down
            self.name = self.__class__.__name__

            # Set and create the workspace dir.
            self.path = workspaces_dir.joinpath(self.name)
            self.path.mkdir(parents=True, exist_ok=True)

            self.cfg = self.config()

            # Get and set the state if there is one, else create one
            try:
                self.state = LocalState.parse_file(self.path.joinpath("statefile.json"))
            except FileNotFoundError:
                self.state = LocalState(host_pattern=self.cfg.host_pattern)
                self.flush()

            self._initialized = True

    def assert_host_pattern_unchanged(self) -> None:
        """Asserts the host pattern has not changed improperly. If it has, it could
        cause unexpected issues such as hosts being in the state that shouldn't"""
        if self.cfg.host_pattern != self.state.host_pattern:
            raise ClickException(
                (
                    "The workspace's host_pattern has changed since `boardwalk init` was first ran."
                    f' It was "{self.state.host_pattern}" but is now "{self.cfg.host_pattern}".'
                    " Run `boardwalk workspace reset` and then `boardwalk init`. Or, change it back"
                )
            )

    @abstractmethod
    def config(self) -> WorkspaceConfig:
        """Required user method. Sets the WorkspaceConfig"""
        raise NotImplementedError

    def flush(self):
        """Flush workspace state to disk"""
        # The statefile is first written to a temp file so that failures in flushing
        # will not corrupt an existing statefile
        with Path(
            NamedTemporaryFile(
                mode="wb", delete=False, dir=self.path, prefix="statefile.json."
            ).name
        ) as tf:
            tf.write_text(self.state.json())
            tf.rename(self.path.joinpath("statefile.json"))

    def reset(self):
        """Resets active workspace. Configuration is retained but other state is lost"""
        # We try to get a mutex on the workspace so we don't reset a workspace that has something running
        self.mutex()
        self.state = LocalState(host_pattern=self.cfg.host_pattern)
        self.flush()
        self.unmutex()

    def mutex(self):
        """
        Method to try and prevent multiple parallel operations on the same
        workspace. Should be called any time we are making changes to the workspace
        """
        try:
            self.path.joinpath("workspace.mutex").touch(exist_ok=False)
        except FileExistsError:
            raise ClickException("Workspace is locked by another operation")

    def has_mutex(self):
        """Checks if the workspace has a mutex. Returns True if so"""
        return self.path.joinpath("workspace.mutex").exists()

    def unmutex(self):
        """Removes the mutex created by mutex method, if any"""
        try:
            self.path.joinpath("workspace.mutex").unlink(missing_ok=True)
        except WorkspaceNotFound:
            pass

    def catch(self):
        """Catche workspace workflow at next host"""
        self.path.joinpath("catch.lock").touch()

    def caught(self):
        """Checks if workspace is caught. Returns true if it is"""
        return self.path.joinpath("catch.lock").exists()

    def release(self):
        """Removes workspace workflow catch if set"""
        self.path.joinpath("catch.lock").unlink(missing_ok=True)

    @staticmethod
    def use(name: str):
        """Sets the active workspace"""
        try:
            ws = get_ws()
            # Check if the active Workspace is mutexed
            if ws.has_mutex():
                raise ClickException(
                    "Workspace is locked by another operation. `boardwalk workspace use` cannot be called while the workspace is locked"
                )
        except NoActiveWorkspace:
            pass
        except WorkspaceNotFound:
            pass

        # Check if the workspace exists
        if not Workspace.exists(name):
            raise WorkspaceNotFound(
                f'Workspace "{name}" doesn\'t exist in Boardwalkfile.py. List workspaces with `boardwalk workspace list`'
            )

        # Create the workspace directory.
        workspaces_dir.mkdir(parents=True, exist_ok=True)

        # Set the selected workspace as the active workspace
        active_workspace_file.write_text(name)

        # Try to initialize the newly active workspace
        ws = get_ws()

    @staticmethod
    def exists(name: str) -> bool:
        """Checks if a Workspace subclass exists by name"""
        workspace_names: list[str] = []
        for workspace in Workspace.__subclasses__():
            workspace_names.append(workspace.__qualname__)
        if name in workspace_names:
            return True
        return False

    @staticmethod
    def fetch_subclass(name: str) -> Callable[..., Workspace]:
        """Returns a subclass by name"""
        for workspace in Workspace.__subclasses__():
            if str(workspace.__qualname__) == name:
                return workspace
        raise WorkspaceNotFound(f"No Workspace exists matching {name}")


def path(file_path: str) -> str:
    """Helper to get absolute path from a string with a relative path and return as a string"""
    if not Path(file_path).exists():
        raise FileNotFoundError(f"{file_path} does not exist")
    return str(Path(file_path).absolute())
