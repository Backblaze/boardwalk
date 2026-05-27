"""
Configurable Slack advice for recognized error messages.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

from pydantic import PrivateAttr, ValidationError, field_validator

from boardwalkd.protocol import ProtocolBaseModel, WorkspaceEvent

REGEX_FLAGS = re.IGNORECASE | re.DOTALL


class SlackErrorAdviceRule(ProtocolBaseModel):
    """A Slack advice rule that matches error messages using regex patterns."""

    name: str
    patterns: list[str]
    message: str
    _compiled_patterns: list[re.Pattern[str]] = PrivateAttr(default_factory=list)

    @field_validator("patterns")
    @classmethod
    def validate_patterns(cls, patterns: list[str]) -> list[str]:
        for pattern in patterns:
            try:
                re.compile(pattern, flags=REGEX_FLAGS)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern {pattern!r}: {e}") from e
        return patterns

    def model_post_init(self, __context: Any) -> None:
        self._compiled_patterns = [re.compile(pattern, flags=REGEX_FLAGS) for pattern in self.patterns]

    def matches(self, event_message: str) -> bool:
        return all(pattern.search(event_message) for pattern in self._compiled_patterns)


class SlackErrorAdviceConfig(ProtocolBaseModel):
    """Top-level Slack advice configuration."""

    rules: list[SlackErrorAdviceRule] = []


class SlackErrorAdviceConfigError(ValueError):
    """Raised when Slack advice configuration cannot be loaded."""


def parse_slack_error_advice_config(config_path: str | Path | None) -> list[SlackErrorAdviceRule]:
    """Parses Slack error advice rules from a TOML config file."""
    if not config_path:
        return []

    path = Path(config_path)
    try:
        with path.open("rb") as config_file:
            parsed = tomllib.load(config_file)
        return SlackErrorAdviceConfig.model_validate(parsed).rules
    except (OSError, tomllib.TOMLDecodeError, ValidationError) as e:
        raise SlackErrorAdviceConfigError(f"Invalid Slack error advice configuration in {path}: {e}") from e


def matching_error_advice(event: WorkspaceEvent, rules: list[SlackErrorAdviceRule]) -> list[SlackErrorAdviceRule]:
    """Returns Slack advice rules matching an error event."""
    if event.severity != "error":
        return []
    return [rule for rule in rules if rule.matches(event.message)]
