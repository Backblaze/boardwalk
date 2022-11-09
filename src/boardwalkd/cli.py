"""
This file contains the boardwalkd CLI code
"""
import asyncio
import re
from importlib.metadata import version as lib_version
from pathlib import Path

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
    "--auth-expire-days",
    help=(
        "The number of days login tokens and user API keys are valid before"
        " they expire"
    ),
    type=float,
    default=14,
    show_default=True,
)
@click.option(
    "--auth-method",
    help=(
        "Enables an authentication method for the web UI. The API always requires"
        " authentication, however without this option configured a predictable"
        " anonymous user will be used. The method is supplied as a string"
        " argument. The BOARDWALK_SECRET environment variable must be set for any"
        " method to work except for 'anonymous'; it is the key used to sign"
        " secure strings, such as auth cookies and API keys\n\n"
        "Available auth methods:\n\n"
        "anonymous\n\n"
        "All requests are performed as an 'anonymous' default user\n\n"
        "google_oauth\n\n"
        "Uses Google Oauth2 to identify users by their Google account email address."
        " BOARDWALK_GOOGLE_OAUTH_CLIENT_ID and BOARDWALK_GOOGLE_OAUTH_SECRET"
        " environment variables must be set. The authorized redirect URI should be"
        " https://<hostname>/auth/login"
    ),
    type=click.Choice(
        ["anonymous", "google_oauth"],
        case_sensitive=False,
    ),
    default="anonymous",
    show_default=True,
)
@click.option(
    "--develop/--no-develop",
    default=False,
    help="Runs the server in development mode with auto-reloading and tracebacks",
    show_default=True,
)
@click.option(
    "--host-header-pattern",
    help=(
        "A valid python regex pattern to match accepted Host header values."
        " This prevents DNS rebinding attacks when the pattern is appropriately scoped"
    ),
    type=str,
    required=True,
)
@click.option(
    "--port",
    help=(
        "The non-TLS port number the server binds to. If --tls-port is"
        " specified the server will redirect UI requests to the TLS port and"
        " API requests to this port will be rejected"
    ),
    type=int,
    required=True,
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
    "--tls-crt",
    help=("Path to TLS certificate chain file for use along with --tls-port"),
    type=click.Path(exists=True, readable=True),
    default=None,
)
@click.option(
    "--tls-key",
    help=("Path to TLS key file for use along with --tls-port"),
    type=click.Path(exists=True, readable=True),
    default=None,
)
@click.option(
    "--tls-port",
    help=(
        "The TLS port number the server binds to. When configured, UI requests"
        " to the non-TLS port (--port) will be redirected to this TLS port and"
        " API requests to the non-TLS port will be rejected. When --tls-port is"
        " configured, --tls-crt and --tls-key must also be supplied"
    ),
    type=int,
    default=None,
)
@click.option(
    "--url",
    help="The base URL where the server can be reached",
    type=str,
    required=True,
)
def serve(
    auth_expire_days: float,
    auth_method: str,
    develop: bool,
    host_header_pattern: str,
    port: int,
    slack_error_webhook_url: str,
    slack_webhook_url: str,
    tls_crt: str | None,
    tls_key: str | None,
    tls_port: int | None,
    url: str,
):
    """Runs the server"""
    # Validate host_header_pattern
    try:
        host_header_regex = re.compile(host_header_pattern)
    except re.error:
        raise ClickException("Host pattern regex invalid")

    # Validate TLS configuration (key and cert paths are already validated by click)
    if tls_port is not None:
        try:
            assert tls_crt
            assert tls_key
        except AssertionError:
            raise ClickException(
                (
                    "--tls-crt and --tls-key paths must be supplied when a"
                    " --tls-port is configured"
                )
            )

    asyncio.run(
        run(
            auth_expire_days=auth_expire_days,
            auth_method=auth_method,
            develop=develop,
            host_header_pattern=host_header_regex,
            port_number=port,
            slack_error_webhook_url=slack_error_webhook_url,
            slack_webhook_url=slack_webhook_url,
            tls_crt_path=tls_crt,
            tls_key_path=tls_key,
            tls_port_number=tls_port,
            url=url,
        )
    )


@cli.command(
    "version",
)
def version():
    """Prints the boardwalk module version number and exits"""
    click.echo(lib_version("boardwalk"))
