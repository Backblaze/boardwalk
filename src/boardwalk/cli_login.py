"""
login CLI subcommand
"""
import asyncio
import click

from boardwalk.manifest import get_boardwalkd_url
from boardwalkd.protocol import Client


@click.command(
    "login",
    short_help="Logs into the API",
)
def login():
    url = get_boardwalkd_url()
    client = Client(url)
    asyncio.run(client.api_login())
