from urllib.parse import urlparse

import pytest

import boardwalkd.broadcast as broadcast
import boardwalkd.server as server
from boardwalkd.broadcast import handle_auth_login_broadcast


@pytest.mark.anyio
async def test_notify_auth_login_resolves_deployment_user_email_for_slack_mention(monkeypatch):
    captured = {}

    async def fake_slack_user_mention_for_email(email, slack_bot_token):
        captured["lookup"] = (email, slack_bot_token)
        return "<@U123>"

    async def fake_handle_auth_login_broadcast(**kwargs):
        captured["broadcast"] = kwargs

    monkeypatch.setattr(server, "slack_user_mention_for_email", fake_slack_user_mention_for_email)
    monkeypatch.setattr(server, "handle_auth_login_broadcast", fake_handle_auth_login_broadcast)

    await server.notify_auth_login(
        login_url="https://boardwalk.example/api/auth/login?id=abc",
        auth_context={"deployment_user_email": "lo@example.com"},
        settings={
            "slack_webhook_url": "https://hooks.example/general",
            "slack_error_webhook_url": "https://hooks.example/error",
            "slack_bot_token": "xoxb-test",
            "url": urlparse("https://boardwalk.example"),
        },
    )

    assert captured["lookup"] == ("lo@example.com", "xoxb-test")
    assert captured["broadcast"]["slack_user_mention"] == "<@U123>"


@pytest.mark.anyio
async def test_handle_auth_login_broadcast_includes_notifying_block(monkeypatch):
    captured = {}

    class FakeWebhookClient:
        def __init__(self, url):
            captured["url"] = url

        async def send(self, blocks):
            captured["blocks"] = blocks

    monkeypatch.setattr(broadcast, "AsyncWebhookClient", FakeWebhookClient)

    await handle_auth_login_broadcast(
        login_url="https://boardwalk.example/api/auth/login?id=abc",
        auth_context={"deployment_user_email": "lo@example.com"},
        webhook_url="https://hooks.example/general",
        error_webhook_url="https://hooks.example/error",
        server_url="https://boardwalk.example",
        slack_user_mention="<@U123>",
    )

    block_text = [block.text.text for block in captured["blocks"] if getattr(block, "text", None)]

    assert captured["url"] == "https://hooks.example/error"
    assert "*Notifying:* <@U123>" in block_text
