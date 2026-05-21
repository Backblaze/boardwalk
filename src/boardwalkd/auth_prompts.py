from collections.abc import Collection
from datetime import UTC, datetime

from pydantic import BaseModel, Field


class AuthLoginPrompt(BaseModel, extra="forbid"):
    """Runtime-only auth login prompt displayed in the boardwalkd UI."""

    client_id: str
    login_url: str
    auth_context: dict[str, str] = Field(default_factory=dict)
    created_time: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def workspace(self) -> str:
        return self.auth_context.get("workspace", "")


active_auth_prompts: dict[str, AuthLoginPrompt] = {}


def set_auth_prompt(client_id: str, login_url: str, auth_context: dict[str, str]) -> AuthLoginPrompt:
    prompt = AuthLoginPrompt(client_id=client_id, login_url=login_url, auth_context=auth_context)
    active_auth_prompts[client_id] = prompt
    return prompt


def clear_auth_prompt(client_id: str) -> None:
    active_auth_prompts.pop(client_id, None)


def prompts_by_workspace() -> dict[str, list[AuthLoginPrompt]]:
    grouped: dict[str, list[AuthLoginPrompt]] = {}
    for prompt in active_auth_prompts.values():
        if not prompt.workspace:
            continue
        grouped.setdefault(prompt.workspace, []).append(prompt)
    return grouped


def orphan_auth_prompts(known_workspace_names: Collection[str]) -> list[AuthLoginPrompt]:
    return [
        prompt
        for prompt in active_auth_prompts.values()
        if not prompt.workspace or prompt.workspace not in known_workspace_names
    ]
