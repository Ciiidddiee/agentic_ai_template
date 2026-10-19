# aikit.evals

Offline and online evaluation of a configured app. Run it with `aikit eval`.

| File | Contents |
|---|---|
| `runner.py` | `run_evals()`: loads JSONL datasets from `evals.datasets` in the config, runs each case through the flow, scores it, and writes `.aikit/evals/eval-<timestamp>.json` |
| `rag_metrics.py` | `recall_at_k`, `citation_precision`, `keyword_coverage`, `faithfulness` (LLM judge, only with `evals.judge`) |
| `agent_metrics.py` | `tool_recall`, `tool_precision`, `task_success` |

## Dataset fields

- **RAG cases:** `question`, `expected_sources`, `must_include`, `k`, `forbidden_sources` (fails on an ACL leak), `groups`, `min_recall`.
- **Agent cases:** `input`, `expected_tools`, `forbidden_tools`, `must_include`, `expected_status` (for example `awaiting_approval`).

The kind of each case is detected from its fields, or set with `kind:` in the config.

In CI, use `aikit eval --min-pass-rate 0.9` to fail the build on regressions.
