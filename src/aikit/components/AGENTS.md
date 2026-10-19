# AGENTS.md: src/aikit/components (adapters)

Applies to everything under `src/aikit/components/`. Also follow [../AGENTS.md](../AGENTS.md) and the root [AGENTS.md](../../../AGENTS.md).

## Writing a component

```python
from __future__ import annotations

from aikit.core.errors import ConfigError
from aikit.core.ports import Embedder
from aikit.core.registry import register


@register("vector_store", "pgvector")
class PgVectorStore:
    """One line shown by `aikit components`."""

    def __init__(
        self, dsn: str, table: str = "chunks", embedder: Embedder | None = None
    ) -> None: ...  # typed params = config schema; port-typed params accept "@name" refs

    async def search(self, vector, *, top_k=5, filters=None, groups=None):
        try:
            import psycopg  # optional extra: import lazily
        except ImportError as exc:
            raise ConfigError("pgvector needs psycopg: install aikit[pgvector]") from exc
        ...
```

## Checklist

- [ ] Implements every method of the port in `core/ports.py` (async where the port is async).
- [ ] Registered with `@register(kind, name)` and imported in the folder's `__init__.py`.
- [ ] No `**kwargs` in `__init__` (parameters are validated with `extra="forbid"`).
- [ ] Network clients are created lazily and closed in `async def aclose()`.
- [ ] Stores enforce `groups` ACLs inside `search` / `keyword_search`.
- [ ] A new `llm` or `embedder` type still works under `--offline`, which swaps in the `fake` type.
- [ ] Contract test subclass added in `tests/contract/`.
- [ ] Row added to the folder's `README.md` and to `components/README.md`.
