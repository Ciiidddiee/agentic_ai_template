from __future__ import annotations

import pytest

from aikit.components.guardrails.max_length import MaxLengthGuardrail
from aikit.components.guardrails.output_schema import OutputSchemaGuardrail
from aikit.components.guardrails.pii_redact import PiiRedactGuardrail
from aikit.core.context import RunContext
from aikit.core.errors import ConfigError, GuardrailViolationError

CTX = RunContext()


async def test_pii_redaction() -> None:
    guard = PiiRedactGuardrail()
    text = (
        "Mail jane.doe@acme.com, card 4111 1111 1111 1111, ssn 123-45-6789, "
        "call 555-123-4567. Order 1234567890123 total 120."
    )
    out = await guard.apply(text, stage="input", ctx=CTX)
    assert "[REDACTED_EMAIL]" in out
    assert "[REDACTED_CARD]" in out
    assert "[REDACTED_SSN]" in out
    assert "[REDACTED_PHONE]" in out
    assert "1234567890123" in out  # fails the Luhn check, so it is not a card
    assert "120" in out


async def test_custom_pii_patterns() -> None:
    guard = PiiRedactGuardrail(patterns={"EMPLOYEE": r"\bEMP-\d{5}\b"})
    assert await guard.apply("EMP-12345", stage="input", ctx=CTX) == "[REDACTED_EMPLOYEE]"


async def test_max_length_blocks_or_truncates() -> None:
    with pytest.raises(GuardrailViolationError):
        await MaxLengthGuardrail(max_chars=5).apply("too long", stage="input", ctx=CTX)
    truncate = MaxLengthGuardrail(max_chars=3, action="truncate")
    assert await truncate.apply("abcdef", stage="input", ctx=CTX) == "abc"


async def test_output_schema() -> None:
    guard = OutputSchemaGuardrail(model="project.domain.refunds:RefundRequest")
    ok = await guard.apply(
        '```json\n{"order_total": 10, "days_since_purchase": 1}\n```', stage="output", ctx=CTX
    )
    assert '"order_total":10.0' in ok
    with pytest.raises(GuardrailViolationError):
        await guard.apply("not json", stage="output", ctx=CTX)


def test_output_schema_bad_path() -> None:
    with pytest.raises(ConfigError):
        OutputSchemaGuardrail(model="project.domain.refunds")
