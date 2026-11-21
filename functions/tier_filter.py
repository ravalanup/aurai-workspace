"""
title: Aurai Tier Filter
author: Aurai Platform
version: 0.1.0
description: Checks messages against the workspace's risk tier before they reach the gateway. Blocks or warns when a message carries a classification marker the tier does not allow. The gateway still masks PII; this filter is an early, cheap check for content that should not be sent at all.
requirements:
"""

import re
from typing import Any

from pydantic import BaseModel, Field

# Classification markers people put on documents. Matched as whole phrases, case-insensitively.
MARKERS = {
    "restricted": re.compile(r"\b(restricted|strictly confidential|secret)\b", re.IGNORECASE),
    "confidential": re.compile(r"\b(confidential|internal use only|company confidential)\b", re.IGNORECASE),
}

# What the workspace does when a marker is found, by risk tier. Higher tiers are stricter.
POLICY = {
    "T0": {"restricted": "block", "confidential": "allow"},
    "T1": {"restricted": "block", "confidential": "warn"},
    "T2": {"restricted": "block", "confidential": "warn"},
    "T3": {"restricted": "block", "confidential": "block"},
}


def classify(text: str) -> list[str]:
    """Return the marker levels found in the text, most severe first."""
    return [level for level, pattern in MARKERS.items() if pattern.search(text)]


def decide(tier: str, text: str) -> tuple[str, str | None]:
    """Return (action, level) where action is allow, warn or block."""
    rules = POLICY.get(tier, POLICY["T3"])  # an unknown tier gets the strictest rules
    for level in classify(text):
        action = rules[level]
        if action != "allow":
            return action, level
    return "allow", None


class Filter:
    class Valves(BaseModel):
        priority: int = Field(default=0, description="Filter order; lower runs first")
        tier: str = Field(default="T1", description="Risk tier of this workspace's gateway team (T0 to T3)")
        max_message_chars: int = Field(default=20000, description="Messages longer than this are rejected")

    def __init__(self) -> None:
        self.valves = self.Valves()

    async def inlet(self, body: dict[str, Any], __user__: dict | None = None, __event_emitter__=None) -> dict[str, Any]:
        """Runs before the request is sent to the model. Raise to block."""
        last_user = next((m for m in reversed(body.get("messages", [])) if m.get("role") == "user"), None)
        if last_user is None:
            return body
        text = _text_of(last_user.get("content"))

        if len(text) > self.valves.max_message_chars:
            raise Exception(f"This message is longer than the {self.valves.max_message_chars} character limit.")

        action, level = decide(self.valves.tier, text)
        if action == "block":
            raise Exception(
                f"This workspace is rated {self.valves.tier} and cannot accept content marked {level}. "
                "Remove the content or use an approved channel for this material."
            )
        if action == "warn" and __event_emitter__ is not None:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"This message looks {level}. Make sure you may share it with this assistant.",
                        "done": True,
                    },
                }
            )
        return body

    async def outlet(self, body: dict[str, Any], __user__: dict | None = None) -> dict[str, Any]:
        return body


def _text_of(content: Any) -> str:
    """Message content is a string or a list of typed parts."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(part.get("text", "") for part in content if isinstance(part, dict))
    return ""
