"""
workspace CLI subcommand group
"""

import click
from loguru import logger

from boardwalk.app_exceptions import BoardwalkException
from boardwalk.manifest import ManifestNotFound, NoActiveWorkspace, Workspace, WorkspaceNotFound, get_ws


@click.group(short_help="Subcommand group for working with workspaces")
def workspace():
    pass


@workspace.command("show", help="Displays the active workspace")
def workspace_show():
    """Gets and prints the active workspace"""
    try:
        ws = get_ws()
    except NoActiveWorkspace as e:
        raise BoardwalkException(e.message)
    click.echo(ws.name)


def workspace_use_completion(ctx, param, incomplete):
    """Allows click to perform shell completion for workspace names in `boardwalk workspace use`"""
    try:
        try:
            get_ws()
        except NoActiveWorkspace:
            pass

        return sorted(
            [name for name in [i.__qualname__ for i in Workspace.__subclasses__()] if name.startswith(incomplete)]
        )
    except ManifestNotFound:
        return []


@workspace.command(
    "use",
    short_help="Sets the active workspace",
)
@click.argument("workspace_name", shell_complete=workspace_use_completion)
def workspace_use(workspace_name: str):
    Workspace.use(workspace_name)
    ws = get_ws()
    logger.info(f"Using workspace: {ws.name}")


@workspace.command("list", help="Lists available workspaces from the Boardwalkfile.py")
def workspace_list():
    try:
        get_ws()
    except NoActiveWorkspace:
        pass
    except WorkspaceNotFound:
        pass
    workspace_names: list[str] = [i.__qualname__ for i in Workspace.__subclasses__()]
    workspace_names.sort()
    for name in workspace_names:
        click.echo(name)


@workspace.command("reset", short_help="Resets active workspace")
@click.confirmation_option(prompt="Are you sure you want to reset the active workspace?")
def workspace_reset():
    """Resets/clears the active workspace state"""
    try:
        ws = get_ws()
    except NoActiveWorkspace as e:
        raise BoardwalkException(e.message)
    logger.info(f"Using workspace: {ws.name}")
    ws.reset()


@workspace.command("dump")
def workspace_dump():
    """Prints the active workspace's state to stdout as JSON"""
    try:
        ws = get_ws()
    except NoActiveWorkspace as e:
        raise BoardwalkException(e.message)
    # We don't want to print the active Workspace name to stdout with a logger
    # because the output wouldn't be valid JSON. So we use click.echo() to simply
    # write to stderr
    click.echo(f"Using workspace: {ws.name}", err=True)
    click.echo(ws.state.json())
