"""
login CLI subcommand
"""

import asyncio

import click
from boardwalkd.protocol import Client

from boardwalk.app_exceptions import BoardwalkException
from boardwalk.manifest import get_boardwalkd_url


@click.command("login")
def login():
    """Login to the API"""
    url = get_boardwalkd_url()
    client = Client(url)
    try:
        asyncio.run(client.api_login())
    except ConnectionRefusedError:
        raise BoardwalkException(f"Unable to reach {url}")
