"""
login CLI subcommand
"""
import asyncio

import click
from boardwalkd.protocol import Client

from click import ClickException

from boardwalk.manifest import get_boardwalkd_url


@click.command("login")
def login():
    """Login to the API"""
    url = get_boardwalkd_url()
    client = Client(url)
    try:
        asyncio.run(client.api_login())
    except ConnectionRefusedError:
        raise ClickException(f"Unable to reach {url}")
    click.echo("Authentication successful")
