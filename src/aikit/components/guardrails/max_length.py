from __future__ import annotations

from typing import Literal

from aikit.core.context import RunContext
from aikit.core.errors import GuardrailViolationError
from aikit.core.registry import register


@register("guardrail", "max_length")
class MaxLengthGuardrail:
    """Blocks or truncates text longer than `max_chars`. Protects context windows and costs."""

    name = "max_length"

    def __init__(
        self,
        max_chars: int = 8000,
        stages: list[str] | None = None,
        action: Literal["block", "truncate"] = "block",
    ) -> None:
        self.max_chars = max_chars
        self.stages = frozenset(stages or ["input"])
        self.action = action

    async def apply(self, text: str, *, stage: str, ctx: RunContext) -> str:
        if len(text) <= self.max_chars:
            return text
        if self.action == "truncate":
            return text[: self.max_chars]
        raise GuardrailViolationError(
            f"{stage} is {len(text)} characters; the limit is {self.max_chars}.",
            guardrail=self.name,
            stage=stage,
        )
