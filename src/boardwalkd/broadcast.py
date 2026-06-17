"""
Code for handling server broadcasts
"""

import asyncio
import time
from dataclasses import dataclass

from slack_sdk.models.blocks import (
    MarkdownTextObject,
    SectionBlock,
)
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.webhook.async_client import AsyncWebhookClient
from tornado.log import app_log

from boardwalkd.protocol import WorkspaceEvent
from boardwalkd.slack_error_advice import SlackErrorAdviceRule

AUTH_CONTEXT_LABELS = {
    "workspace": "Workspace",
    "worker_command": "Command",
    "worker_limit": "Limit",
    "worker_username": "User",
    "worker_hostname": "Worker host",
    "deployment_url": "Deployment link",
    "deployment_name": "Deployment name",
    "deployment_number": "Deployment number",
    "deployment_tag": "Deployment tag",
    "deployment_user": "Deployment user",
    "deployment_user_id": "Deployment user ID",
    "deployment_user_email": "Deployment user email",
}

SLACK_USER_LOOKUP_TIMEOUT_SECONDS = 3.0
SLACK_USER_MENTION_CACHE_TTL_SECONDS = 3600.0


@dataclass
class SlackUserMentionCacheEntry:
    mention: str
    expires_at: float


_slack_user_mention_cache: dict[str, SlackUserMentionCacheEntry] = {}


def _auth_login_context_fields(auth_context: dict[str, str], server_url: str) -> list[MarkdownTextObject]:
    """Formats auth login context into Slack fields."""
    fields: list[MarkdownTextObject] = []
    for key, label in AUTH_CONTEXT_LABELS.items():
        value = auth_context.get(key)
        if not value:
            continue
        if key == "workspace":
            value = f"<{server_url}#{value}|{value}>"
        elif key == "deployment_url":
            value = f"<{value}|{value}>"
        fields.append(MarkdownTextObject(text=f"*{label}:*\n{value}"))
    return fields


async def handle_auth_login_broadcast(
    login_url: str,
    auth_context: dict[str, str],
    webhook_url: str | None,
    error_webhook_url: str | None,
    server_url: str,
    slack_user_mention: str | None = None,
):
    """Posts a Slack notification when a worker is waiting for API authentication."""
    webhook_url = error_webhook_url or webhook_url
    if not webhook_url:
        raise ValueError("No slack webhook urls defined")

    slack_message_blocks = [
        SectionBlock(text=MarkdownTextObject(text=":large_yellow_circle: *AUTH LOGIN REQUIRED*")),
        SectionBlock(
            text=MarkdownTextObject(
                text=f"<{login_url}|Open Boardwalk login>\n```\n{login_url}\n```",
            )
        ),
    ]
    if slack_user_mention:
        slack_message_blocks.append(SectionBlock(text=MarkdownTextObject(text=f"*Notifying:* {slack_user_mention}")))

    context_fields = _auth_login_context_fields(auth_context=auth_context, server_url=server_url)
    for i in range(0, len(context_fields), 10):
        slack_message_blocks.append(SectionBlock(fields=context_fields[i : i + 10]))

    webhook_client = AsyncWebhookClient(url=webhook_url)
    await webhook_client.send(blocks=slack_message_blocks)


async def handle_slack_broadcast(
    event: WorkspaceEvent,
    workspace: str,
    webhook_url: str | None,
    error_webhook_url: str | None,
    server_url: str,
    error_advice: list[SlackErrorAdviceRule] | None = None,
    slack_user_mention: str | None = None,
):
    """Handles posting events to slack. If an error_webhook_url is not None,
    then all error events will be posted there"""
    if not (webhook_url or error_webhook_url):
        raise ValueError("No slack webhook urls defined")

    if event.severity == "info":
        slack_message_severity = ":large_blue_circle: INFO"
    elif event.severity == "success":
        slack_message_severity = ":large_green_circle: SUCCESS"
    elif event.severity == "error":
        slack_message_severity = ":red_circle: ERROR"
    else:
        raise ValueError(f"Event severity is invalid: {event.severity}")

    MAX_PAYLOAD_LENGTH: int = 2000
    msg = event.message
    if len(msg) > MAX_PAYLOAD_LENGTH:
        msg = (
            msg[:MAX_PAYLOAD_LENGTH]
            + f"\n[ ... message truncated at {MAX_PAYLOAD_LENGTH} characters; see log for {len(msg) - MAX_PAYLOAD_LENGTH} remaining character(s) ... ]"
        )

    slack_message_blocks = [
        SectionBlock(
            fields=[
                MarkdownTextObject(text=f"*{slack_message_severity}*"),
                MarkdownTextObject(text=f"*<{server_url}#{workspace}|{workspace}>*"),
            ]
        ),
        SectionBlock(text=MarkdownTextObject(text=f"```\n{msg}\n```")),
    ]
    if event.severity == "error" and slack_user_mention:
        slack_message_blocks.append(SectionBlock(text=MarkdownTextObject(text=f"*Notifying:* {slack_user_mention}")))
    for advice in error_advice or []:
        slack_message_blocks.append(
            SectionBlock(text=MarkdownTextObject(text=f":information_source: *{advice.name}*\n{advice.message}"))
        )

    if error_webhook_url and event.severity == "error":
        webhook_client = AsyncWebhookClient(url=error_webhook_url)
        await webhook_client.send(blocks=slack_message_blocks)
    elif webhook_url:
        webhook_client = AsyncWebhookClient(url=webhook_url)
        await webhook_client.send(blocks=slack_message_blocks)


async def slack_user_mention_for_email(email: str | None, slack_bot_token: str | None) -> str | None:
    """Resolves a Slack mention for an email address using the configured bot token."""
    if not email or not slack_bot_token or "@" not in email:
        return None

    normalized_email = email.strip().lower()
    cached_entry = _slack_user_mention_cache.get(normalized_email)
    if cached_entry:
        if cached_entry.expires_at > time.monotonic():
            return cached_entry.mention
        del _slack_user_mention_cache[normalized_email]

    client = AsyncWebClient(token=slack_bot_token)
    try:
        response = await asyncio.wait_for(
            client.users_lookupByEmail(email=normalized_email),
            timeout=SLACK_USER_LOOKUP_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        app_log.warning(f"Timed out resolving Slack user mention for {normalized_email}")
        return None
    except Exception as e:
        app_log.warning(f"Could not resolve Slack user mention for {normalized_email}: {e}")
        return None
    user_id = response.get("user", {}).get("id")
    mention = f"<@{user_id}>" if user_id else None
    if mention:
        _slack_user_mention_cache[normalized_email] = SlackUserMentionCacheEntry(
            mention=mention,
            expires_at=time.monotonic() + SLACK_USER_MENTION_CACHE_TTL_SECONDS,
        )
    return mention
