# AGENTS.md: src/aikit (kernel)

Applies to everything under `src/aikit/`. Also follow the root [AGENTS.md](../../AGENTS.md).

## Layers

`lint-imports` enforces these rules in CI. Check `.importlinter` before adding imports.

| Package | May import |
|---|---|
| `aikit.core` | stdlib, pydantic, yaml only |
| `aikit.components.*` | `aikit.core` (+ httpx, optional extras imported lazily) |
| `aikit.flows` | `aikit.core` |
| `aikit.observability` | `aikit.core` (+ structlog, optional OpenTelemetry) |
| `aikit.runtime` | everything except `serving` / `evals` |
| `aikit.evals`, `aikit.serving` | everything |

```python
# ❌ a flow depending on a concrete adapter
from aikit.components.retrievers.hybrid import HybridRetriever

# ✅ depend on the port; the builder injects the configured implementation
from aikit.core.ports import Retriever


class MyFlow(BaseFlow):
    def __init__(self, retriever: Retriever) -> None: ...
```

## Rules

- A new capability needs a Protocol in `core/ports.py`, an entry in `KIND_BY_PORT`, and a contract suite in `tests/contract/`.
- Shared helpers between components go in `components/_<name>.py`, not in `core`.
- `Policy` checks stay inside flows, not hooks, so plugins can't disable them.
- Changes to `core/` are API changes for every app built on the template. Keep them backwards compatible, or record an ADR in `docs/decisions/`.
- The `RunEvent` types (`start`, `retrieval`, `token`, `tool_call`, `tool_result`, `approval_required`, `answer`, `error`, `done`) are a contract with the CLI, API, and evals. Don't rename them.
