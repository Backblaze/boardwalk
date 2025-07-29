"""
Code for handling server broadcasts
"""

from slack_sdk.models.blocks import (
    MarkdownTextObject,
    SectionBlock,
)
from slack_sdk.webhook.async_client import AsyncWebhookClient

from boardwalkd.protocol import WorkspaceEvent


async def handle_slack_broadcast(
    event: WorkspaceEvent,
    workspace: str,
    webhook_url: str | None,
    error_webhook_url: str | None,
    server_url: str,
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

    if error_webhook_url and event.severity == "error":
        webhook_client = AsyncWebhookClient(url=error_webhook_url)
        await webhook_client.send(blocks=slack_message_blocks)
    elif webhook_url:
        webhook_client = AsyncWebhookClient(url=webhook_url)
        await webhook_client.send(blocks=slack_message_blocks)
