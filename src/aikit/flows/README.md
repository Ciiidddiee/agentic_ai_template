# aikit.flows

Use cases built only on `core` interfaces. Flows never import concrete components.

| Type | File | What it does |
|---|---|---|
| `ingest` | `ingest.py` | Load → chunk → embed → upsert. Idempotent through content-hash chunk ids, removes stale chunks per source, and with `prune: true` deletes sources that no longer exist. |
| `rag` | `rag.py` | Optional query rewrite → retrieve → rerank → answer with `[n]` citations. Streams tokens, applies `min_score` / `no_answer_text`, and can require citations. |
| `agent` | `agent.py` | Tool-calling loop under a `Policy`. Runs read-only tools in parallel, pauses for approval on write/code tools (stored in a `RunStore`), and resumes with `resume(run_id, approvals)`. |

`base.py` contains `BaseFlow`. Subclasses implement `_events(input, ctx)`. The base class provides:

- the `start` event;
- error-to-status mapping: `blocked`, `budget_exceeded`, `timeout`, `error`;
- guardrails and hooks;
- `run()`, which collects the event stream into a `RunResult`.

Every flow emits the same `RunEvent` types: `start`, `retrieval`, `token`, `tool_call`, `tool_result`, `approval_required`, `answer`, `error`, and `done`. The CLI, API, and eval runner depend on this contract, so keep it stable.

To add a flow, subclass `BaseFlow`, register it with `@register("flow", "<name>")`, and add an integration test.
