"""
workspace CLI subcommand group
"""

import inspect
import os
from pathlib import Path

import click
from loguru import logger
from rich import print
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from boardwalk import WorkspaceConfig
from boardwalk.app_exceptions import BoardwalkException
from boardwalk.manifest import (
    ManifestNotFound,
    NoActiveWorkspace,
    PlaybookJob,
    TaskJob,
    Workflow,
    Workspace,
    WorkspaceNotFound,
    get_ws,
)


@click.group(short_help="Subcommand group for working with workspaces")
def workspace() -> None:
    pass


@workspace.command("show", help="Displays the active workspace")
def workspace_show() -> None:
    """Gets and prints the active workspace"""
    try:
        ws = get_ws()
    except NoActiveWorkspace as e:
        raise BoardwalkException(e.message)
    click.echo(ws.name)


def _shell_complete_workspaces(ctx: click.Context, param, incomplete: str) -> list[str]:
    """Allows click to perform shell completion for :class:`Workspace` names"""
    try:
        try:
            get_ws()
        except NoActiveWorkspace:
            pass

        return sorted(
            [
                name
                for name in [i.__qualname__ for i in Workspace.__subclasses__()]
                if name.lower().startswith(incomplete.lower())
            ]
        )
    except ManifestNotFound:
        return []


@workspace.command(
    "use",
    short_help="Sets the active workspace",
)
@click.argument("workspace_name", shell_complete=_shell_complete_workspaces)
def workspace_use(workspace_name: str) -> None:
    Workspace.use(workspace_name)
    ws = get_ws()
    logger.info(f"Using workspace: {ws.name}")


def _construct_job_tree(
    jobs: TaskJob | PlaybookJob | tuple[TaskJob | PlaybookJob, ...] | list[TaskJob | PlaybookJob],
) -> Tree:
    """Constructs an ordered list of Jobs as a single-level :class:`Tree`, without a root node

    :returns: the ordered list of Jobs based on the input
    :rtype: :class:`Tree`
    """
    job_tree = Tree("", hide_root=True)
    if not isinstance(jobs, list | tuple | set):
        jobs = [jobs]
    for idx, job in enumerate(jobs):
        job_tree.add(Text(f"{idx + 1}. ", style="cyan").append(job.__class__.__name__, style="default"))
    return job_tree


@workspace.command("list", short_help="Lists available workspaces from the Boardwalkfile.py")
@click.option(
    "--jobs/--no-jobs",
    type=bool,
    default=False,
    show_default=True,
    help="Also show Jobs associated with returned Workflows",
)
@click.option(
    "--config/--no-config",
    type=bool,
    default=False,
    show_default=True,
    help="Also show the configuration for returned Workflows",
)
@click.argument("workspace", required=False, type=str, default=None, shell_complete=_shell_complete_workspaces)
def workspace_list(jobs: bool = False, config: bool = False, workspace: str | None = None) -> None:
    """Lists available Workspaces within the Boardwalkfile.py, optionally showing
    Workspace configuration and Jobs assigned to the Workspace's Workflow.

    If `WORKSPACE` is provided, filters the displayed data to Workspaces which start with the supplied string, case-insensitively.
    """
    try:
        get_ws()
    except NoActiveWorkspace:
        pass
    except WorkspaceNotFound:
        pass
    workspace_list_output_root = Tree(label="", hide_root=True)
    cwd = Path(os.getcwd())

    # Create a sorted dictionary of all subclasses of the Workspace class
    workspace_classes_dict: dict[str, type[Workspace]] = {
        k: v for k, v in sorted({i.__name__: i for i in Workspace.__subclasses__()}.items())
    }

    _should_display_any_workspace_details = any([config, jobs])
    warned_about_dynamic_class_source = False
    # Iterate through all subclasses of the dictionary
    for workspace_class_name, workspace_type in workspace_classes_dict.items():
        # If the `workspace` argument is defined, and the current `workspace_class_name` does not begin with that string (case insensitive), skip to the next item
        if workspace is not None and not workspace_class_name.lower().startswith(workspace.lower()):
            continue

        workspace_tree_node = workspace_list_output_root.add(
            f"{workspace_class_name}", expanded=_should_display_any_workspace_details
        )

        if _should_display_any_workspace_details:
            # Instantiate the workspace to access its configuration
            workspace_class_instance = workspace_type()
            workspace_config: WorkspaceConfig = workspace_class_instance.config()

            # Process the workflow data
            workflow: Workflow = getattr(workspace_config, "workflow")

            workspace_configuration_detail_table = Table(show_header=False, box=None)

            if config:
                workspace_configuration_detail_table.add_column("Label", style="bold", justify="right")
                workspace_configuration_detail_table.add_column("Details")

                try:
                    path_to_ws_file = Path(inspect.getfile(workspace_class_instance.__class__)).relative_to(cwd)
                except ValueError:
                    path_to_ws_file = Path(inspect.getfile(workspace_class_instance.__class__))
                # Store the name of the module, and check (and notify) if the class appears to be sourced from `abc.py`
                if os.path.basename(path_to_ws_file) == "abc.py":
                    logger.warning(
                        f'Workspace {workspace_class_name} seems to be sourced from abc.py. Is this a dynamically generated class? (Hint: did you specify `"__module__": __name__` when instantiating this Workspace?)'
                    )
                    warned_about_dynamic_class_source = True

                workspace_configuration_detail_table.add_row(
                    "Workspace Source Module",
                    Text(str(path_to_ws_file), style="magenta", no_wrap=False, overflow="fold"),
                )

                workspace_configuration_detail_table.add_row("Default Sort Order", workspace_config.default_sort_order)
                workspace_configuration_detail_table.add_row("Host Pattern", workspace_config.host_pattern)
                workspace_configuration_detail_table.add_row(
                    "Requires --limit?",
                    Text(
                        "Yes" if workspace_config.require_limit else "No",
                        style="red" if workspace_config.require_limit else "dim",
                    ),
                )

            if config or jobs:
                workspace_configuration_detail_table.add_row("Workflow", workflow.__class__.__name__)

            if jobs:
                # Parse and add the main workflow job(s)
                workspace_configuration_detail_table.add_row(
                    "Main Workflow Jobs", _construct_job_tree(jobs=workflow.jobs())
                )

                # Parse and add the exit workflow job(s), if any
                exit_jobs_tree = _construct_job_tree(jobs=workflow.exit_jobs())
                workspace_configuration_detail_table.add_row(
                    "Exit Workflow Jobs",
                    exit_jobs_tree if exit_jobs_tree.children else Text("No exit jobs defined", style="dim"),
                )

            workspace_config_panel = Panel.fit(
                workspace_configuration_detail_table,
                title=f":hammer_and_wrench: Workspace {' / '.join([s for s in ['Configuration' if config else None, 'Jobs' if jobs else None] if s is not None])}",
            )
            workspace_tree_node.add(workspace_config_panel)

    print(workspace_list_output_root)
    if warned_about_dynamic_class_source:
        logger.warning(
            "One or more classes couldn't have their exact source module identified; see warning(s) above output"
        )


@workspace.command("reset", short_help="Resets active workspace")
@click.confirmation_option(prompt="Are you sure you want to reset the active workspace?")
def workspace_reset() -> None:
    """Resets/clears the active workspace state"""
    try:
        ws = get_ws()
    except NoActiveWorkspace as e:
        raise BoardwalkException(e.message)
    logger.info(f"Using workspace: {ws.name}")
    ws.reset()


@workspace.command("dump")
def workspace_dump() -> None:
    """Prints the active workspace's state to stdout as JSON"""
    try:
        ws = get_ws()
    except NoActiveWorkspace as e:
        raise BoardwalkException(e.message)
    # We don't want to print the active Workspace name to stdout with a logger
    # because the output wouldn't be valid JSON. So we use click.echo() to simply
    # write to stderr
    click.echo(f"Using workspace: {ws.name}", err=True)
    click.echo(ws.state.model_dump_json())
