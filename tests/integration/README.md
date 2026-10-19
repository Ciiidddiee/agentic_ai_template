# tests/integration

End-to-end tests of the real project profiles, using offline fakes and a temporary index.

| File | Covers |
|---|---|
| `test_rag_flow.py` | Citations, idempotent re-ingest, token streaming order, ACL filtering, `min_score` no-answer, output guardrail buffering, input guardrail blocking |
| `test_agent_flow.py` | Tool loop, approval pause/resume/reject, allowlist, unknown tools, max steps, token budget, tool timeouts, parallel read-only tools, memory |
| `test_agentic_rag.py` | `project/app.yaml` end to end; the eval datasets pass offline |
| `test_cli.py` | `validate`, `ingest`, `ask`, `run --auto-approve`, `components`, exit code 2 on bad config |
| `test_api.py` | Health, ingest/query, SSE, groups from headers driving ACLs, approval round trip, validation errors |

These tests rely on `project/data/samples/` and `project/evals/datasets/`. When you replace the example app, update or replace these tests as well.
