# AGENTS.md: project/ (the app)

Applies to everything under `project/`. Also follow the root [AGENTS.md](../AGENTS.md).

## Where things go

- `domain/`: business rules as pure, typed Python (pydantic models and functions). No LLM, HTTP, or `aikit` imports.
- `tools/`: thin `@tool` wrappers that validate input, call `domain/`, and return JSON-serialisable data.
- `prompts/`: Markdown prompts. Guide the model, but never rely on a prompt to enforce a rule.
- `data/`: documents for ingest. Use front matter `acl: [group]` for restricted content. Only `samples/` is committed.
- `evals/datasets/`: add a case for every bug or new behaviour.

```python
# ❌ side effect without declaring it; logic inside the tool
@tool()
def refund(order_id: str, amount: float) -> dict:
    if amount > 500:
        ...


# ✅ declare capabilities; delegate rules to domain
@tool(capabilities=["write"], requires_approval=True)
def issue_refund(order_id: str, amount: float, ctx: RunContext) -> dict:
    """Issue a refund to the original payment method. Requires human approval."""
    return payments.issue_refund(order_id=order_id, amount=amount).model_dump()
```

- The tool docstring is what the model reads to decide when to call the tool. Keep it to one clear sentence.
- New tool modules must be imported in `project/tools/__init__.py`.

## YAML config (`app.yaml`, `profiles/*.yaml`)

- Top-level keys: `extends`, `app`, `imports`, `plugins`, `components`, `ingest`, `flow`, `observability`, `evals`. Unknown keys are errors.
- Every spec has a `type` (registry name). A string is shorthand: `- issue_refund` means `{type: issue_refund}`.
- Reference shared components with `"@name"` (quote it: `@` is reserved in YAML). Write `"@@x"` for a literal `@x`.
- Components whose key isn't a kind name need `kind:`, e.g. `fast_llm: {kind: llm, type: openai_compat, ...}`.
- Secrets and endpoints come from the environment: `${LLM_TOKEN}`, or `${LLM_BASE_URL:-http://localhost:8000/v1}`. Never hard-code them.
- Paths are relative to the repo root.
- Changing a component's `type` in a child profile replaces the whole spec. Setting a key to `null` removes it.

```yaml
extends: project/profiles/agentic_rag.yaml
components:
  llm:
    model: ${LLM_MODEL:-gpt-oss-120b}
flow:
  policy:
    max_steps: 6
```

Verify changes with `aikit --offline validate`. Find valid parameters with `aikit components --schema <kind>/<type>`.
