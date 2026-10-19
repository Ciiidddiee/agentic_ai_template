# Adding components

Everything the config can reference is a registered component. The registry key is `(kind, name)`. Kinds are `llm`, `embedder`, `vector_store`, `loader`, `chunker`, `retriever`, `reranker`, `memory`, `tool`, `guardrail`, `hook`, `run_store`, and `flow`.

## A project tool

For most tools, write a typed function. The schema comes from the signature, the description from the docstring, and a `ctx` parameter (hidden from the model) gives access to the caller's identity.

```python
# project/tools/orders.py
from aikit import RunContext, tool
from project.domain.orders import find_order


@tool(capabilities=["read"])
def get_order_status(order_id: str, ctx: RunContext) -> dict:
    """Return the shipping status of an order."""
    return find_order(order_id, requested_by=ctx.user_id).model_dump()
```

Import the module from `project/tools/__init__.py`, then reference it in config:

```yaml
flow:
  tools:
    - get_order_status
```

Use `capabilities=["write"]` (or `requires_approval=True`) for anything with side effects. The default policy then pauses the run for human approval.

Use a `BaseTool` subclass when the tool needs its own configuration (base URLs, clients). See `aikit/components/tools/http.py`.

## A new adapter (vector DB, model API, reranker, ...)

1. Implement the interface from `aikit/core/ports.py`. Annotate constructor parameters with real types; the builder validates config against them and uses port annotations (such as `embedder: Embedder`) to resolve `"@name"` references and nested specs.
2. Register it:

   ```python
   from aikit.core.ports import Embedder
   from aikit.core.registry import register


   @register("vector_store", "pgvector")
   class PgVectorStore:
       def __init__(self, dsn: str, table: str = "chunks", dimensions: int = 1024) -> None: ...
       async def upsert(self, chunks): ...
       async def search(self, vector, *, top_k=5, filters=None, groups=None): ...
       async def delete(self, ids): ...
       async def ids(self, filters=None): ...
       async def count(self): ...
       async def aclose(self): ...  # optional; called on shutdown
   ```

3. Import optional dependencies inside methods, not at module top level, so installs without the extra still work.
4. Add a contract test: subclass the matching suite in `tests/contract/` and provide a fixture. The adapter counts as supported once the shared tests pass.

   ```python
   class TestPgVectorStore(VectorStoreContract):
       @pytest.fixture
       def store(self, tmp_path):
           return PgVectorStore(dsn=os.environ["TEST_PG_DSN"], table=f"t_{uuid4().hex[:8]}")
   ```

5. Enforce ACLs inside `search` (use `aikit.core.filters.acl_allows` or the database equivalent). Never filter after returning results.

Put adapters for one app in `project/`. Put adapters that several apps need in a plugin package (below) or in `src/aikit/components/` if you maintain the shared kernel.

## A plugin package

A plugin is a normal Python package that exposes entry points. Installing it does nothing by itself: an app must also allowlist it.

```toml
# pyproject.toml of acme-aikit-pgvector
[project.entry-points."aikit.vector_store"]
pgvector = "acme_aikit_pgvector:PgVectorStore"

# or register several components by importing a module:
[project.entry-points."aikit.plugins"]
acme_search = "acme_aikit_search.components"
```

```yaml
# project/app.yaml
plugins: [pgvector]
components:
  vector_store: {type: pgvector, dsn: "${PG_DSN}"}
```

Publish plugins to your internal package index only, with review. Loading a plugin runs its code.

## A hook

Hooks see every LLM call, tool call, retrieval, and run event, and can transform data. They cannot bypass the policy.

```python
from aikit.core.hooks import Hook
from aikit.core.registry import register


@register("hook", "audit_log")
class AuditLogHook(Hook):
    def __init__(self, topic: str) -> None:
        self.topic = topic

    async def after_tool(self, call, result, ctx):
        publish(self.topic, {"user": ctx.user_id, "tool": call.name, "error": result.is_error})
        return result
```

```yaml
flow:
  hooks:
    - {type: audit_log, topic: ai-audit}
```

## A persistent run store

Paused agent runs default to memory, so they are lost on restart. Implement `RunStore` (`save`, `load`, `delete` of a JSON-serialisable dict), register it as kind `run_store`, and set `flow.run_store`.

## A new flow

Subclass `aikit.flows.base.BaseFlow`, implement `_events(input, ctx)` as an async generator that yields `RunEvent`s and finishes with `self._done(result)`, and register it as kind `flow`. Error handling, guardrails, hooks, and telemetry come from the base class, and the CLI, API, and eval runner work with it unchanged.
