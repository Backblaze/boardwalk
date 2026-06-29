import pytest

import boardwalkd.broadcast as broadcast
from boardwalkd.broadcast import handle_auth_login_broadcast


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
