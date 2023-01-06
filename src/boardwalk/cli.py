"""
This is the main file for handling the CLI
"""
from __future__ import annotations

import logging
import os
import signal
import sys
from distutils.util import strtobool
from importlib.metadata import version as lib_version
from typing import Literal, TYPE_CHECKING

import click

from boardwalk.app_exceptions import BoardwalkException

from boardwalk.cli_catch import catch, release
from boardwalk.cli_init import init
from boardwalk.cli_login import login
from boardwalk.cli_run import check, run
from boardwalk.cli_workspace import workspace
from boardwalk.manifest import (
    get_ws,
    ManifestNotFound,
    NoActiveWorkspace,
    WorkspaceNotFound,
)

if TYPE_CHECKING:
    from typing import Any

logger = logging.getLogger(__name__)

terminating = False


def handle_signal(sig: int, frame: Any):
    """
    Handles process exit signals so the CLI has a better chance of cleaning up
    after itself. Boardwalk needs to perform certain cleanup actions in most
    cases, and this function helps resist unclean exits. It cannot handle
    signals sent to child processes (ansible-playbook)
    """
    global terminating
    logger.warn(f"Received signal {sig}")
    if not terminating:
        terminating = True
        raise KeyboardInterrupt
    else:
        logger.warn("Boardwalk is already terminating")


@click.group()
@click.option(
    "--debug/--no-debug",
    "-D/-nD",
    help=(
        "Whether or not output debug messages. Alternatively may be set with"
        " the BOARDWALK_DEBUG=1 environment variable"
    ),
    default=False,
    show_default=True,
)
@click.pass_context
def cli(ctx: click.Context, debug: bool | Literal[0, 1]):
    """
    Boardwalk is a linear remote execution workflow engine built on top of Ansible.
    See the README.md @ https://github.com/Backblaze/boardwalk for more info

    To see more info about any subcommand, do `boardwalk <subcommand> --help`
    """
    try:
        debug = strtobool(os.environ["BOARDWALK_DEBUG"])
    except KeyError:
        pass
    except ValueError:
        raise BoardwalkException(
            "BOARDWALK_DEBUG env variable has an invalid boolean value"
        )

    if debug:
        loglevel = logging.DEBUG
        logformat = "%(levelname)s:%(name)s:%(threadName)s:%(message)s"
    else:
        loglevel = logging.INFO
        logformat = "%(levelname)s:%(name)s:%(message)s"

    logging.basicConfig(
        format=logformat,
        handlers=[logging.StreamHandler(sys.stdout)],
        level=loglevel,
    )

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
