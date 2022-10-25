"""
login CLI subcommand
"""
import asyncio
from pathlib import Path

import click
from boardwalkd.protocol import Client

from click import ClickException

from boardwalk.manifest import get_boardwalkd_url


@click.command(
    "login",
    short_help="Login to the API",
)
def login():
    url = get_boardwalkd_url()
    client = Client(url)
    try:
        token = asyncio.run(client.api_login())
    except ConnectionRefusedError:
        raise ClickException(f"Unable to reach {url}")
    client.api_token_file.write_text(token)
    click.echo("Authentication successful")
