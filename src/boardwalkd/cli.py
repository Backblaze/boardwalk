"""
This file contains the boardwalkd CLI code
"""

import asyncio
import json
import re
import sys
from datetime import UTC, datetime
from importlib.metadata import version as lib_version
from pathlib import Path

import click
from email_validator import EmailNotValidError, validate_email
from loguru import logger

from boardwalk.app_exceptions import BoardwalkException
from boardwalkd.server import run
from boardwalkd.slack_error_advice import SlackErrorAdviceConfigError, parse_slack_error_advice_config
from boardwalkd.snapshot import load_inventory_context
from boardwalkd.snapshot import sanitize_status_snapshot as sanitize_status_snapshot_data

CONTEXT_SETTINGS: dict = dict(
    auto_envvar_prefix="BOARDWALKD",
)


@click.group()
def cli():
    """
    Boardwalkd is the server component of Boardwalk.
    See the README.md @ https://github.com/Backblaze/boardwalk for more info

    To see more info about any subcommand, execute `boardwalkd <subcommand> --help`
    """
    pass


@cli.command(context_settings=CONTEXT_SETTINGS)
@click.option(
    "--auth-login-slack-notify/--no-auth-login-slack-notify",
    help="Post a Slack message when a worker is waiting for an API auth login",
    type=bool,
    default=False,
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--auth-expire-days",
    help=("The number of days login tokens and user API keys are valid before they expire"),
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
        " BOARDWALKD_GOOGLE_OAUTH_CLIENT_ID and BOARDWALKD_GOOGLE_OAUTH_SECRET"
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
    "--demo/--no-demo",
    default=False,
    help="Loads generic demo workspace rows into the `boardwalkd` state, only if the state is empty",
    show_default=True,
)
@click.option(
    "--develop-snapshot",
    type=click.Path(exists=True, readable=True, dir_okay=False),
    default=None,
    help="Seed development workspaces from a redacted /api/workspaces/status snapshot",
)
@click.option(
    "--host-header-pattern",
    help=(
        "A valid python regex pattern to match accepted Host header values."
        " This prevents DNS rebinding attacks when the pattern is appropriately scoped"
        " Requests reaching the server that don't match this pattern will return a 404"
    ),
    type=str,
    required=True,
)
@click.option(
    "--owner",
    help=(
        "A default admin user. Every time the server starts up, this user will"
        " be enabled and added to the admin role. This option must be supplied"
        " when --auth-method is anything other than 'anonymous'. The purpose of"
        " the owner is to have an initial admin user available at first start"
        " and to avoid lock-outs"
    ),
    type=str,
    default=None,
)
@click.option(
    "--port",
    help=("The non-TLS port number the server binds to. --port and/or --tls-port must be configured"),
    type=int,
    default=None,
)
@click.option(
    "--slack-webhook-url",
    help="A Slack webhook URL to broadcast all key events to",
    type=str,
    default=None,
    show_envvar=True,
)
@click.option(
    "--slack-error-webhook-url",
    help=(
        "A Slack webhook URL to broadcast error events to."
        " If defined, errors will not be sent to the URL defined by --slack-webhook-url"
    ),
    type=str,
    default=None,
    show_envvar=True,
)
@click.option(
    "--slack-app-token",
    help=(
        "A Slack App Token for the Slack App this Boardwalkd instance is to connect to."
        " If specified, --slack-bot-token must also be provided."
    ),
    type=str,
    default=None,
    show_envvar=True,
)
@click.option(
    "--slack-bot-token",
    help=("A Slack OAuth Bot Token for the Slack App this Boardwalkd instance is to connect to."),
    type=str,
    default=None,
    show_envvar=True,
)
@click.option(
    "--slack-error-advice-config",
    help="Path to a TOML config file with advice rules to append to matching Slack error notifications.",
    type=click.Path(exists=True, readable=True, dir_okay=False),
    default=None,
    show_envvar=True,
)
@click.option(
    "--slack-slash-command-prefix",
    help=(
        "The prefix to use in front of Boardwalk slash commands in Slack (e.g., /PREFIX-version). Needs to match the prefix supplied in the Slack App configuration."
    ),
    type=str,
    default="brdwlk",
    show_default=True,
    show_envvar=True,
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
        "The TLS port number the server binds to. When configured, the --url"
        " option must have an https:// scheme. When --tls-port is configured,"
        " --tls-crt and --tls-key must also be supplied"
    ),
    type=int,
    default=None,
)
@click.option(
    "--theme-static-path",
    help="Directory of private theme assets to serve under /theme-static/",
    type=click.Path(exists=True, file_okay=False, readable=True),
    default=None,
    show_envvar=True,
)
@click.option(
    "--theme-css-url",
    help="Optional CSS URL loaded after the bundled boardwalkd stylesheet",
    type=str,
    default="",
    show_envvar=True,
)
@click.option(
    "--theme-logo-url",
    help="Optional logo image URL for the top-left brand mark",
    type=str,
    default="",
    show_envvar=True,
)
@click.option(
    "--theme-logo-alt",
    help="Alt text for the themed logo; defaults to the brand name in templates",
    type=str,
    default="",
    show_envvar=True,
)
@click.option(
    "--theme-brand-name",
    help="Brand name rendered in the dashboard header and page title",
    type=str,
    default="Boardwalk",
    show_envvar=True,
)
@click.option(
    "--jenkins-job-url",
    help="Base Jenkins job URL used to link workspace build numbers to build pages",
    type=str,
    default="",
    show_envvar=True,
)
@click.option(
    "--url",
    help=(
        "The base URL where the server can be reached. UI Requests that do not"
        " match the scheme or host:port of this URL will automatically be redirected"
    ),
    type=str,
    required=True,
)
@click.option(
    "-v",
    "--verbose",
    count=True,
    default=0,
    help="Whether or not output messages should be verbose. Additional -v's increases the verbosity",
    show_default=True,
    show_envvar=True,
    type=click.IntRange(min=0, max=2, clamp=True),
)
@click.option(
    "--workspace-status-json/--no-workspace-status-json",
    help="Provides the status of all workspaces at /api/workspaces/status via a JSON object. This endpoint does not require authentication.",
    type=bool,
    default=False,
    show_envvar=True,
)
def serve(
    auth_login_slack_notify: bool,
    auth_expire_days: float,
    auth_method: str,
    develop: bool,
    demo: bool,
    develop_snapshot: str | None,
    host_header_pattern: str,
    owner: str | None,
    port: int | None,
    slack_error_webhook_url: str,
    slack_webhook_url: str,
    slack_app_token: str | None,
    slack_bot_token: str | None,
    slack_error_advice_config: str | None,
    slack_slash_command_prefix: str,
    theme_static_path: str | None,
    theme_css_url: str,
    theme_logo_url: str,
    theme_logo_alt: str,
    theme_brand_name: str,
    jenkins_job_url: str,
    tls_crt: str | None,
    tls_key: str | None,
    tls_port: int | None,
    url: str,
    verbose: int,
    workspace_status_json: bool,
):
    """Runs the `boardwalkd` server until terminated"""
    logger.enable("boardwalkd")
    logger.remove()
    loglevel = "INFO" if verbose == 0 else "DEBUG" if verbose == 1 else "TRACE"
    logger.add(sys.stdout, level=loglevel)
    logger.info(f"boardwalkd, version {lib_version('boardwalk')}, is now starting...")
    logger.info(f"Log level is {loglevel}")

    logger.warning("boardwalkd is running in development mode, which should not be used in a production environment")

    if develop_snapshot and not develop:
        raise BoardwalkException("--develop-snapshot requires --develop")
    if develop_snapshot and demo:
        raise BoardwalkException("--demo cannot be combined with --develop-snapshot")

    # Validate host_header_pattern
    try:
        host_header_regex = re.compile(host_header_pattern)
    except re.error:
        raise BoardwalkException("Host pattern regex invalid")

    # Validate any port is configured
    if not (port or tls_port):
        raise BoardwalkException("One or both of --port or --tls-port must be configured")

    # If there is no TLS port then reject setting a TLS key and cert
    if (not tls_port) and (tls_crt or tls_key):
        raise BoardwalkException("--tls-crt and --tls-key should not be configured unless --tls-port is also set")

    # Validate TLS configuration (key and cert paths are already validated by click)
    if tls_port is not None:
        try:
            assert tls_crt
            assert tls_key
        except AssertionError:
            raise BoardwalkException("--tls-crt and --tls-key paths must be supplied when a --tls-port is configured")

    # Validate --owner
    if owner:
        try:
            validate_email(owner, check_deliverability=False)
        except EmailNotValidError:
            raise BoardwalkException("Email addressed passed to --owner is invalid")
    elif auth_method != "anonymous":
        raise BoardwalkException("--owner must be defined when --auth-method is not 'anonymous'")
    else:
        owner = "anonymous@example.com"

    # Validate Slack app/bot token
    if (not slack_bot_token) and slack_app_token:
        raise BoardwalkException("If --slack-app-token is supplied, --slack-bot-token must also be supplied")

    try:
        slack_error_advice_rules = parse_slack_error_advice_config(slack_error_advice_config)
        logger.info(
            f"{len(slack_error_advice_rules)} error advice rule(s) were loaded from {slack_error_advice_config}"
        )
    except SlackErrorAdviceConfigError as e:
        raise BoardwalkException(str(e))

    # This pattern lets us keep the actual `run()` function able to be called by
    # pytest without blocking the main thread. Here, we're fine with it, cause
    # this command spawns and runs the server via the CLI
    async def start_server_and_wait():
        await run(
            auth_expire_days=auth_expire_days,
            auth_login_slack_notify=auth_login_slack_notify,
            auth_method=auth_method,
            develop=develop,
            demo=demo,
            develop_snapshot_path=develop_snapshot,
            host_header_pattern=host_header_regex,
            owner=owner,
            port_number=port,
            slack_app_token=slack_app_token,
            slack_bot_token=slack_bot_token,
            slack_error_advice_rules=slack_error_advice_rules,
            slack_error_webhook_url=slack_error_webhook_url,
            slack_webhook_url=slack_webhook_url,
            slack_slash_command_prefix=slack_slash_command_prefix,
            theme_static_path=theme_static_path,
            theme_css_url=theme_css_url,
            theme_logo_url=theme_logo_url,
            theme_logo_alt=theme_logo_alt,
            theme_brand_name=theme_brand_name,
            jenkins_job_url=jenkins_job_url,
            tls_crt_path=tls_crt,
            tls_key_path=tls_key,
            tls_port_number=tls_port,
            url=url,
            workspace_status_json=workspace_status_json,
        )
        await asyncio.Event().wait()

    # Spawn the server and run until terminated
    asyncio.run(start_server_and_wait())


@cli.command("sanitize-status-snapshot")
@click.argument("source", type=click.Path(exists=True, readable=True, dir_okay=False))
@click.argument("destination", type=click.Path(dir_okay=False))
@click.option(
    "--captured-at",
    type=str,
    default=None,
    help="ISO-8601 timestamp to use as the snapshot capture time. Defaults to now.",
)
@click.option(
    "--preserve-identifiers/--redact-identifiers",
    default=False,
    help="Keep workspace/user/host identifiers for private local replay.",
    show_default=True,
)
@click.option(
    "--inventory-json",
    type=click.Path(exists=True, readable=True, dir_okay=False),
    default=None,
    help="Optional ansible-inventory --list --export JSON used to derive ui_group from group ancestry.",
)
def sanitize_status_snapshot(
    source: str,
    destination: str,
    captured_at: str | None,
    preserve_identifiers: bool,
    inventory_json: str | None,
):
    """Converts a /api/workspaces/status JSON snapshot for local development replay."""
    now = datetime.fromisoformat(captured_at).replace(tzinfo=UTC) if captured_at else None
    raw_snapshot = json.loads(Path(source).read_text())
    sanitized = sanitize_status_snapshot_data(
        raw_snapshot,
        now=now,
        preserve_identifiers=preserve_identifiers,
        inventory=load_inventory_context(inventory_json),
    )
    Path(destination).write_text(json.dumps(sanitized, indent=2, sort_keys=True) + "\n")
    click.echo(f"Wrote sanitized snapshot to {destination}")


@cli.command(
    "version",
)
def version():
    """Prints the boardwalk module version number and exits"""
    click.echo(lib_version("boardwalk"))
