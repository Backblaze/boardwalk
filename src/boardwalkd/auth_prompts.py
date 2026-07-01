from collections.abc import Collection
from datetime import UTC, datetime
from urllib.parse import urlparse

from loguru import logger
from pydantic import BaseModel, Field, field_validator
from pydantic_core import PydanticCustomError


class AuthLoginPrompt(BaseModel, extra="forbid"):
    """Runtime-only auth login prompt displayed in the boardwalkd UI."""

    client_id: str
    login_url: str
    auth_context: dict[str, str | None] = Field(default_factory=dict)
    created_time: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def workspace(self) -> str:
        return self.auth_context.get("workspace", "")  # pyright: ignore[reportReturnType]

    @field_validator("auth_context", mode="before")
    @classmethod
    def validate_auth_context(cls, auth_context: dict[str, str]):
        """Field validator for `auth_context`.

        Currently validates:
          - `deployment_url` - Ensures URL scheme is valid"""
        valid_url_schemes: list[str] = ["http", "https"]
        # Check to see if the deployment_url both: a) Exists, and b) is an expected scheme. If not, raise a validation error
        if (deployment_url := auth_context.get("deployment_url")) and (
            scheme := urlparse(deployment_url).scheme
        ) not in valid_url_schemes:
            logger.error(
                f"Invalid `deployment_url` scheme received from {auth_context.get('worker_username', 'unknown')}@{auth_context.get('worker_hostname', 'unknown')}; expected one of {valid_url_schemes}; received: {scheme}"
            )
            raise PydanticCustomError(
                "invalid_AuthLoginPrompt_deployment_url_scheme",
                "auth_context['deployment_url'] failed to validate due to invalid scheme; expected one of {valid_schemes}; parsed [{invalid_scheme}]; the `deployment_url` was: `{deployment_url}`",
                {
                    "valid_schemes": valid_url_schemes,
                    "invalid_scheme": scheme,
                    "deployment_url": deployment_url,
                },
            )
        return auth_context


active_auth_prompts: dict[str, AuthLoginPrompt] = {}


def set_auth_prompt(client_id: str, login_url: str, auth_context: dict[str, str | None]) -> AuthLoginPrompt:
    """Stores a pending authentication prompt for a given authentication request"""
    prompt = AuthLoginPrompt(client_id=client_id, login_url=login_url, auth_context=auth_context)
    active_auth_prompts[client_id] = prompt
    return prompt


def clear_auth_prompt(client_id: str) -> None:
    """Removes the authentication prompt for a specified client_id"""
    active_auth_prompts.pop(client_id, None)


def prompts_by_workspace() -> dict[str, list[AuthLoginPrompt]]:
    """Returns a dictionary, with the key as the workspace name, and the value as a list of pending authentication prompts"""
    grouped: dict[str, list[AuthLoginPrompt]] = {}
    for prompt in active_auth_prompts.values():
        if not prompt.workspace:
            continue
        grouped.setdefault(prompt.workspace, []).append(prompt)
    return grouped


def orphan_auth_prompts(known_workspace_names: Collection[str]) -> list[AuthLoginPrompt]:
    """Generates a list of pending auth prompts for as-of-yet unknown workspaces."""
    return [
        prompt
        for prompt in active_auth_prompts.values()
        if not prompt.workspace or prompt.workspace not in known_workspace_names
    ]
