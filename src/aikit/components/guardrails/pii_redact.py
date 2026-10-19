from __future__ import annotations

import re

from aikit.core.context import RunContext
from aikit.core.registry import register

DEFAULT_PATTERNS: dict[str, str] = {
    "EMAIL": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    "CARD": r"\b(?:\d[ -]?){12,18}\d\b",
    "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
    "PHONE": r"(?:\+\d{1,3}[\s.-]?)?\(?\b\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b",
}


def _luhn_valid(candidate: str) -> bool:
    digits = [int(c) for c in candidate if c.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    for i, digit in enumerate(reversed(digits)):
        if i % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


@register("guardrail", "pii_redact")
class PiiRedactGuardrail:
    """Replaces emails, card numbers (Luhn-checked), SSNs, and phone numbers with placeholders.

    Add organisation-specific identifiers (employee ids, account numbers) via `patterns`.
    """

    name = "pii_redact"

    def __init__(
        self,
        stages: list[str] | None = None,
        patterns: dict[str, str] | None = None,
        replacement: str = "[REDACTED_{label}]",
    ) -> None:
        self.stages = frozenset(stages or ["input", "context", "tool_result"])
        self.replacement = replacement
        self.patterns = [
            (label, re.compile(pattern))
            for label, pattern in {**DEFAULT_PATTERNS, **(patterns or {})}.items()
        ]

    async def apply(self, text: str, *, stage: str, ctx: RunContext) -> str:
        for label, pattern in self.patterns:
            if label == "CARD":
                text = pattern.sub(
                    lambda m, lbl=label: (
                        self.replacement.format(label=lbl)
                        if _luhn_valid(m.group(0))
                        else m.group(0)
                    ),
                    text,
                )
            else:
                text = pattern.sub(self.replacement.format(label=label), text)
        return text
