# aikit.components

Adapters that implement the interfaces in `core/ports.py`. Each one registers itself with `@register(kind, name)`, and config files select it by `type: <name>`. Run `aikit components` to list them, or `aikit components --schema <kind>/<name>` to see a component's parameters.

| Folder | Kind | Registered names |
|---|---|---|
| [`llm/`](llm/README.md) | `llm` | `openai_compat`, `fake` |
| [`embeddings/`](embeddings/README.md) | `embedder` | `openai_compat`, `fake` |
| [`vectorstores/`](vectorstores/README.md) | `vector_store` | `in_memory` |
| [`loaders/`](loaders/README.md) | `loader` | `text`, `markdown`, `pdf`, `docx` |
| [`chunkers/`](chunkers/README.md) | `chunker` | `recursive`, `markdown` |
| [`retrievers/`](retrievers/README.md) | `retriever` | `dense`, `hybrid` |
| [`rerankers/`](rerankers/README.md) | `reranker` | `passthrough`, `llm_rerank` |
| [`memory/`](memory/README.md) | `memory` | `buffer`, `summary` |
| [`tools/`](tools/README.md) | `tool` | `retriever_tool`, `http` |
| [`guardrails/`](guardrails/README.md) | `guardrail` | `pii_redact`, `max_length`, `output_schema` |

Shared helpers (private, underscore-prefixed):

- `_openai_http.py`: `OpenAICompatClient`, with retries on 408/409/429/5xx, `Retry-After` support, and SSE streaming.
- `_text.py`: tokenizer, cosine similarity, and BM25 (pure Python).

## Adding a component

1. Create a module in the matching folder and import it from the folder's `__init__.py`.
2. Use typed constructor parameters. They become the config schema.
3. Import optional dependencies inside methods, and raise `ConfigError` with an install hint if they're missing.
4. Add a subclass of the matching contract suite in `tests/contract/` if one exists.

Components must not import `flows`, `observability`, `runtime`, or `serving`. See [docs/adding_components.md](../../../docs/adding_components.md).
