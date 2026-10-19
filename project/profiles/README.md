# project/profiles

Config layers that `app.yaml` (or `--config`) builds on through `extends:`.

| File | Flow | Contents |
|---|---|---|
| `base.yaml` | — | Shared components: `llm`, `embedder`, `vector_store`, `retriever`, `reranker`, plus `ingest:`, `imports:`, and `observability:` |
| `rag.yaml` | `rag` | Retrieve, rerank, and answer with citations. PII redaction and a length limit. |
| `agent.yaml` | `agent` | Tool-calling agent with the refund tools, buffer memory, and a policy |
| `agentic_rag.yaml` | `agent` | Agent plus `retriever_tool` (`search_policies`). Default for `app.yaml`. |

## Merge rules

- Mappings are merged deeply, and later files win.
- If a component's `type` changes, its spec is replaced instead of merged, so parameters from the old type don't leak.
- Setting a key to `null` removes it.
- `${VAR}` and `${VAR:-default}` read from the environment or `.env`. Missing variables without a default are listed in the error.
- `--offline` swaps every `llm` and `embedder` for `fake` before interpolation, so offline runs need no secrets.

Try a profile without editing anything: `aikit -c project/profiles/rag.yaml ask "..."`.
