"""
Code for handling server broadcasts
"""
import json
import logging

from tornado.httpclient import AsyncHTTPClient, HTTPError, HTTPRequest

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
    slack_message_blocks = {
        "blocks": [
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*{slack_message_severity}*",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*<{server_url}#{workspace}|{workspace}>*",
                    },
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"```\n{event.message}\n```",
                },
            },
        ]
    }
    payload = json.dumps(slack_message_blocks)

    async def post_msg(url: str):
        request = HTTPRequest(
            method="POST",
            headers={"Content-Type": "application/json"},
            body=payload,
            url=url,
        )
        client = AsyncHTTPClient()
        try:
            await client.fetch(request)
        except HTTPError as e:
            logging.error(f"slack_webhook:{e}")

    if error_webhook_url and event.severity == "error":
        await post_msg(error_webhook_url)
    elif webhook_url:
        await post_msg(webhook_url)
