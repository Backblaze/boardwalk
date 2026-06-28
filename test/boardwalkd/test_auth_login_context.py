from typing import cast

import tornado.web

from boardwalkd import server


class _FakeRequestHandler:
    """Minimal stand-in exposing get_query_argument for auth_login_context_from_request"""

    def __init__(self, query_args: dict[str, str]):
        self._query_args = query_args

    def get_query_argument(self, name: str, default: str = "") -> str:
        return self._query_args.get(name, default)


def _handler(query_args: dict[str, str]) -> tornado.web.RequestHandler:
    return cast(tornado.web.RequestHandler, _FakeRequestHandler(query_args))


def test_auth_login_context_drops_deployment_url_with_disallowed_scheme():
    # A javascript:/data: URL must be dropped so it cannot be rendered into an
    # <a href> on the dashboard, while the other context fields are preserved
    context = server.auth_login_context_from_request(
        _handler({"workspace": "example", "deployment_url": "javascript:alert(document.domain)"})
    )
    assert "deployment_url" not in context
    assert context["workspace"] == "example"


def test_auth_login_context_keeps_http_and_https_deployment_url():
    # Legitimate worker-supplied deployment URLs are unaffected
    for url in ("https://ci.example/job/1", "http://ci.example/job/1"):
        context = server.auth_login_context_from_request(_handler({"deployment_url": url}))
        assert context["deployment_url"] == url
