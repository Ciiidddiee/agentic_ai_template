# tests/

Everything runs offline in seconds with `poe test` (or `pytest`). No gateway or secrets are needed.

| Folder | What it tests |
|---|---|
| [`unit/`](unit/README.md) | Kernel pieces in isolation: registry, builder, config, policy, chunkers, tooling, guardrails, domain rules, rename script |
| [`contract/`](contract/README.md) | Shared suites every adapter of an interface must pass, plus the OpenAI-compatible adapters against a mock gateway |
| [`integration/`](integration/README.md) | Full profiles end to end with offline fakes: RAG, agent, agentic RAG, the eval suite, CLI, and API |

`conftest.py`:

- Changes into the repo root and clears `AIKIT_CONFIG`, `AIKIT_OFFLINE`, and `LLM_*` connection variables for every test.
- `index_path`: a temporary vector-store file.
- `offline_runtime(config, **overrides)`: builds an offline `Runtime` and closes it after the test.

Conventions: async tests need no marker (`asyncio_mode = auto`). Prefer `FakeLLM(responses=[...])` scripts over heuristics when a test depends on exact model behaviour.
