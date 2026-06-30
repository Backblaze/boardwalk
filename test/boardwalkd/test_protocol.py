import pytest
from pydantic_core import ValidationError

from boardwalkd.protocol import WorkspaceDetails


@pytest.mark.parametrize(
    ("url"),
    [
        pytest.param(""),
        pytest.param("http://jenkins.example.network"),
        pytest.param("https://jenkins.example.network"),
    ],
)
def test_WorkspaceDetails_accepts_deployment_url_with_valid_scheme(url: str):
    """We expect that any valid deployment_url in the auth_context is present from an instantiated :class:`AuthLoginPrompt`"""
    workspace_details = WorkspaceDetails(deployment_url=url)
    assert workspace_details.deployment_url == url


@pytest.mark.parametrize(
    ("url"),
    [
        pytest.param("javascript:alert(document.domain)"),
        pytest.param("data:,Hello%2C%20World%21"),
        pytest.param("httpx://jenkins.example.network"),
    ],
)
def test_WorkspaceDetails_raises_when_invalid_url_scheme_provided(url: str):
    """We expect that any invalid schema in the auth_context's deployment_url is rejected with a Pydantic validation error"""
    with pytest.raises(ValidationError) as exc_info:
        _ = WorkspaceDetails(deployment_url=url)
    errors = exc_info.value.errors()
    assert len(errors) == 1
    assert errors[0]["type"] == "invalid_WorkspaceDetails_deployment_url_scheme"
