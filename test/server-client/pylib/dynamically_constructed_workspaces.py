from typing import TYPE_CHECKING

from boardwalk import TaskJob, Workflow, Workspace, WorkspaceConfig

if TYPE_CHECKING:
    from boardwalk import AnsibleTasksType

NUMBER_OF_GENERIC_WORKSPACES_TO_CREATE: int = 1
GENERIC_WORKSPACE_DOCSTRING: str = """Example dynamically generated workspace.

    This workspace was dynamically generated and injected into the Boardwalkfile.
"""

# Initialize __all__ so 'from module import *' works perfectly
__all__ = []

workspace_names_to_create: dict[str, bool] = {
    "DynamicallyGeneratedWorkspaceBoundToPylibModule": True,
    "DynamicallyGeneratedWorkspaceNotBoundToPylibModule": False,
}


class DynamicallyGeneratedWorkflowWorkflow(Workflow):
    def jobs(self):
        return DynamicallyGeneratedWorkflowJob()


class DynamicallyGeneratedWorkflowJob(TaskJob):
    def tasks(self) -> AnsibleTasksType:
        return [{"ansible.builtin.debug": {"msg": "Hello, Boardwalk!"}}]


for ws_name, should_bind_to_pylib_module in workspace_names_to_create.items():
    class_name = f"{ws_name}"

    def make_config_method():
        def config(self):
            return WorkspaceConfig(
                default_sort_order="ascending",
                host_pattern="all:!switches",
                require_limit=True,
                workflow=DynamicallyGeneratedWorkflowWorkflow(),
            )

        return config

    # Dynamically create the class as appropriate
    if should_bind_to_pylib_module:
        new_class = type(class_name, (Workspace,), {"config": make_config_method(), "__module__": __name__})
    else:
        new_class = type(class_name, (Workspace,), {"config": make_config_method()})
    new_class.__doc__ = GENERIC_WORKSPACE_DOCSTRING

    # Inject the new class into the module's global namespace
    globals()[class_name] = new_class

    # Add the generated class name to __all__
    __all__.append(class_name)  # pyright: ignore[reportUnsupportedDunderAll]
