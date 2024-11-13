"""
This is the main file for handling the CLI
"""

from __future__ import annotations

import signal
import sys
from importlib.metadata import version as lib_version
from typing import TYPE_CHECKING

import click
from loguru import logger  # noqa: F401

from boardwalk.app_exceptions import BoardwalkException
from boardwalk.cli_catch import catch, release
from boardwalk.cli_init import init
from boardwalk.cli_login import login
from boardwalk.cli_run import check, run
from boardwalk.cli_workspace import workspace
from boardwalk.manifest import (
    ManifestNotFound,
    NoActiveWorkspace,
    WorkspaceNotFound,
    get_ws,
)

if TYPE_CHECKING:
    from typing import Any


terminating = False


def handle_signal(sig: int, frame: Any):
    """
    Handles process exit signals so the CLI has a better chance of cleaning up
    after itself. Boardwalk needs to perform certain cleanup actions in most
    cases, and this function helps resist unclean exits. It cannot handle
    signals sent to child processes (ansible-playbook)
    """
    global terminating
    logger.warning(f"Received signal {sig}")
    if not terminating:
        terminating = True
        raise KeyboardInterrupt
    else:
        logger.warning("Boardwalk is already terminating")


@click.group()
@click.option(
    "-v",
    "--verbose",
    count=True,
    default=0,
    envvar="BOARDWALK_VERBOSITY",
    help="Whether or not output messages should be verbose. Additional -v's increases the verbosity",
    show_default=True,
    show_envvar=True,
    type=click.IntRange(min=0, max=5, clamp=True),
)
@click.pass_context
def cli(ctx: click.Context, verbose: int):
    """
    Boardwalk is a linear remote execution workflow engine built on top of Ansible.
    See the README.md @ https://github.com/Backblaze/boardwalk for more info

    To see more info about any subcommand, do `boardwalk <subcommand> --help`
    """
    ctx.ensure_object(dict)

    loglevel = "INFO" if verbose == 0 else "DEBUG" if verbose == 1 else "TRACE"
    ctx.obj["VERBOSITY"] = verbose
    logger.remove()
    logger.add(sys.stdout, level=loglevel)
    if verbose > 0:
        logger.info(f"Log level is {loglevel}")

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGHUP, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    try:
        get_ws()
    except ManifestNotFound:
        # There's not much we can do without a Boardwalkfile.py. Print help and
        # exit if it's missing. The version subcommand is the only one that
        # doesn't need a Boardwalkfile.py
        if ctx.invoked_subcommand == "version":
            return
        click.echo(cli.get_help(ctx))
        raise BoardwalkException("No Boardwalkfile.py found")
    except NoActiveWorkspace:
        return
    except WorkspaceNotFound:
        return


@cli.command(
    "version",
)
def version():
    """Prints the boardwalk module version number and exits"""
    click.echo(lib_version("boardwalk"))


cli.add_command(catch)
cli.add_command(check)
cli.add_command(init)
cli.add_command(login)
cli.add_command(release)
cli.add_command(run)
cli.add_command(workspace)
