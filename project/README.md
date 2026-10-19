# project/

Everything specific to one app lives here. The kernel in `src/` stays generic. The example is "Acme Support", an agentic RAG assistant that answers policy questions and processes refunds with human approval.

| Path | Contents |
|---|---|
| `app.yaml` | **Active config.** It `extends` a profile and overrides values. The CLI and API load it by default (`AIKIT_CONFIG` overrides the path). |
| [`profiles/`](profiles/README.md) | Reusable config layers: `base.yaml` plus one profile per flow shape |
| [`prompts/`](prompts/README.md) | System prompts and templates, referenced by path from config |
| [`tools/`](tools/README.md) | App-specific agent tools (thin wrappers around `domain/`) |
| [`domain/`](domain/README.md) | Business rules as plain Python, no LLM involved |
| [`data/`](data/README.md) | Documents to ingest |
| [`evals/`](evals/README.md) | Golden datasets for `aikit eval` |

## Turning this into your app

1. Replace the documents in `data/` and update the `ingest:` loaders in `profiles/base.yaml`.
2. Choose the flow shape by setting `extends:` in `app.yaml` to `rag`, `agent`, or `agentic_rag`.
3. Rewrite the prompts in `prompts/`.
4. Replace `domain/refunds.py` and `tools/refunds.py` with your own rules and tools, and update `tools/__init__.py`.
5. Write eval cases in `evals/datasets/` and run `aikit --offline eval`, then `aikit eval` against the real gateway.

Config paths are relative to the repository root, which is where you run `aikit`.
