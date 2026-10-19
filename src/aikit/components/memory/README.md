# components/memory

Conversation history keyed by `RunContext.session_id`. Each implements `Memory`: `load(session_id)` and `save(session_id, messages)`.

| Type | File | Notes |
|---|---|---|
| `buffer` | `buffer.py` | Keeps the last `max_messages` messages. `trim_history` starts at a user turn, so tool results are never orphaned. |
| `summary` | `summary.py` | Once history exceeds `max_messages`, keeps the last `keep_last` messages verbatim and folds older ones into an LLM summary (one system message) |

Both are in-process. For multi-replica deployments, add a Redis- or database-backed implementation with the same interface.
