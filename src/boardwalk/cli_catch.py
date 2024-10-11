"""
catch and release CLI subcommands
"""

import click
from loguru import logger

from boardwalk.app_exceptions import BoardwalkException
from boardwalk.manifest import NoActiveWorkspace, get_ws


@click.command(
    "catch",
    short_help="Catch workflow in active workspace",
)
def catch():
    """Creates 'catch' in the active workspace. Workflows will stop at the next host. Catch remains in place until released"""
    try:
        ws = get_ws()
    except NoActiveWorkspace as e:
        raise BoardwalkException(e.message)
    logger.info(f"Using workspace: {ws.name}")
    ws.catch()


@click.command(
    "release",
    short_help="Removes catch from active workspace",
)
def release():
    """Removes catch from active workspace. Any running workflow will resume if it was caught"""
    try:
        ws = get_ws()
    except NoActiveWorkspace as e:
        raise BoardwalkException(e.message)
    logger.info(f"Using workspace: {ws.name}")
    ws.release()
