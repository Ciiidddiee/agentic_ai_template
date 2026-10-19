# project/tools

App-specific agent tools. Each module registers tools on import. `__init__.py` imports them, and `imports: [project.tools]` in `profiles/base.yaml` loads the package.

| Tool | Capabilities | What it does |
|---|---|---|
| `check_refund_eligibility` | `read` | Calls `domain.refunds.evaluate_refund` and returns the decision |
| `issue_refund` | `write`, requires approval | Calls `domain.refunds.issue_refund`; the agent pauses until a human approves |

## Writing a tool

```python
from aikit import RunContext, tool


@tool(capabilities=["read"])
def get_order_status(order_id: str, ctx: RunContext) -> dict:
    """One sentence the model reads to decide when to call this tool."""
    return find_order(order_id, requested_by=ctx.user_id).model_dump()
```

- The argument schema comes from the type hints, and the description from the docstring.
- The `ctx` parameter is hidden from the model and carries the caller's identity and groups.
- Keep tools thin: validate input, call `domain/`, and return JSON-serialisable data.
- Declare `write` for side effects, `network` for external calls, and `pii` if the tool returns personal data.
- Reference tools in config by name (`- get_order_status`). Rename one per flow with `{type: get_order_status, name: order_status}`.
