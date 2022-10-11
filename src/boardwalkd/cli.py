"""
This file contains the boardwalkd CLI code
"""
import asyncio
import re
from importlib.metadata import version as lib_version

import click
from click import ClickException

from boardwalkd.server import run


@click.group()
def cli():
    """
    Boardwalkd is the server component of Boardwalk.
    See the README.md @ https://github.com/Backblaze/boardwalk for more info

    To see more info about any subcommand, do `boardwalkd <subcommand> --help`
    """
    pass


@cli.command()
@click.option(
    "--develop/--no-develop",
    default=False,
    help="Runs the server in development mode with auto-reloading and tracebacks",
    show_default=True,
)
@click.option(
    "--enable-google-oauth/--no-enable-google-oauth",
    help=(
        "Enables Google Oauth2 for the web UI."
        " BOARDWALK_GOOGLE_OAUTH_CLIENT_ID and BOARDWALK_GOOGLE_OAUTH_SECRET"
        " environment variables must be set along with BOARDWALK_SECRET"
    ),
    default=False,
    show_default=True,
)
@click.option(
    "--host-header-pattern",
    help="A valid python regex pattern to match accepted Host header values",
    type=str,
    required=True,
)
@click.option(
    "--port", help="The port number the server binds to", type=int, required=True
)
@click.option(
    "--slack-webhook-url",
    help="A Slack webhook URL to broadcast all key events to",
    type=str,
    default=None,
)
@click.option(
    "--slack-error-webhook-url",
    help=(
        "A Slack webhook URL to broadcast error events to."
        " If defined, errors will not be sent to the URL defined by --slack-webhook-url"
    ),
    type=str,
    default=None,
)
@click.option(
    "--url",
    help="The base URL where the server can be reached",
    type=str,
    required=True,
)
def serve(
    develop: bool,
    enable_google_oauth: bool,
    host_header_pattern: str,
    port: int,
    slack_webhook_url: str,
    slack_error_webhook_url: str,
    url: str,
):
    """Runs the server"""
    try:
        host_header_regex = re.compile(host_header_pattern)
    except re.error:
        raise ClickException("Host pattern regex invalid")

    asyncio.run(
        run(
            develop=develop,
            enable_google_oauth=enable_google_oauth,
            host_header_pattern=host_header_regex,
            port_number=port,
            slack_webhook_url=slack_webhook_url,
            slack_error_webhook_url=slack_error_webhook_url,
            url=url,
        )
    )


@cli.command(
    "version",
)
def version():
    """Prints the boardwalk module version number and exits"""
    click.echo(lib_version("boardwalk"))
