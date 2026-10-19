# components/guardrails

Text checks and transforms. Each implements `Guardrail`: `name`, `stages`, and `apply(text, stage, ctx) -> str`. A guardrail returns a modified string, or raises `GuardrailViolationError` to block the run (status `blocked`).

Stages: `input`, `context` (retrieved chunks), `tool_result`, `output`.

| Type | File | Default stages | Notes |
|---|---|---|---|
| `pii_redact` | `pii_redact.py` | input, context, tool_result | Email, Luhn-checked card numbers, SSN, phone. Add org-specific regexes with `patterns`. |
| `max_length` | `max_length.py` | input | Blocks text over `max_chars`, or truncates it with `action: truncate` |
| `output_schema` | `output_schema.py` | output | Validates JSON output against a pydantic model given as `"module:Class"` |

Configure them under a flow's `guardrails:`. When any guardrail runs at the `output` stage, the RAG flow buffers the answer instead of streaming tokens.
