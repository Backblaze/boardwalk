import pytest
from pydantic_core import ValidationError

from boardwalkd.auth_prompts import AuthLoginPrompt


@pytest.mark.parametrize(
    ("url"),
    [
        pytest.param("", id="url_empty"),
        pytest.param("http://jenkins.example.network", id="scheme_http"),
        pytest.param("https://jenkins.example.network", id="scheme_https"),
    ],
)
def test_AuthLoginPrompt_accepts_deployment_url_with_valid_scheme(url: str):
    """We expect that any valid deployment_url in the auth_context is present from an instantiated :class:`AuthLoginPrompt`"""
    auth_login_prompt = AuthLoginPrompt(
        client_id="123", login_url="https://foobar.example", auth_context=dict({"deployment_url": url})
    )
    assert auth_login_prompt.auth_context["deployment_url"] == url


@pytest.mark.parametrize(
    ("url"),
    [
        pytest.param("javascript:alert(document.domain)", id="scheme_javascript"),
        pytest.param("data:,Hello%2C%20World%21", id="scheme_data"),
        pytest.param("httpx://jenkins.example.network", id="scheme_httpx"),
    ],
)
def test_AuthLoginPrompt_raises_when_invalid_url_scheme_provided(url: str):
    """We expect that any invalid schema in the auth_context's deployment_url is rejected with a Pydantic validation error"""
    with pytest.raises(ValidationError) as exc_info:
        _ = AuthLoginPrompt(
            client_id="123", login_url="https://foobar.example", auth_context=dict({"deployment_url": url})
        )
    errors = exc_info.value.errors()
    assert len(errors) == 1
    assert errors[0]["type"] == "invalid_AuthLoginPrompt_deployment_url_scheme"
