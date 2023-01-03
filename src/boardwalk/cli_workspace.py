"""
workspace CLI subcommand group
"""
import click
from click import ClickException

from boardwalk.manifest import get_ws, NoActiveWorkspace, Workspace, WorkspaceNotFound
from boardwalk.log import boardwalk_logger


@click.group(short_help="Subcommand group for working with workspaces")
def workspace():
    pass


@workspace.command("show", help="Displays the active workspace")
def workspace_show():
    """Gets and prints the active workspace"""
    try:
        ws = get_ws()
    except NoActiveWorkspace as e:
        raise ClickException(e.message)
    click.echo(ws.name)


@workspace.command(
    "use",
    short_help="Sets the active workspace",
)
@click.argument("workspace_name")
def workspace_use(workspace_name: str):
    Workspace.use(workspace_name)
    ws = get_ws()
    boardwalk_logger.info(f"Using workspace: {ws.name}")


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
@click.confirmation_option(
    prompt="Are you sure you want to reset the active workspace?"
)
def workspace_reset():
    """Resets/clears the active workspace state"""
    try:
        ws = get_ws()
    except NoActiveWorkspace as e:
        raise ClickException(e.message)
    boardwalk_logger.info(f"Using workspace: {ws.name}")
    ws.reset()


@workspace.command("dump")
def workspace_dump():
    """Prints the active workspace's state to stdout as JSON"""
    try:
        ws = get_ws()
    except NoActiveWorkspace as e:
        raise ClickException(e.message)
    # We don't want to print the active Workspace name to stdout with a logger
    # because the output wouldn't be valid JSON. So we use click.echo() to simply
    # write to stderr
    click.echo(f"Using workspace: {ws.name}", err=True)
    click.echo(ws.state.json())
