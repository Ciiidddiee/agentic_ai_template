# aikit template

A reusable template for RAG and agentic AI apps that run on an internal, OpenAI-compatible LLM gateway.

Every app is built from the same parts:

- **Components** are swappable adapters (LLM, embedder, vector store, loaders, chunkers, retrievers, rerankers, memory, tools, guardrails). Each implements a small interface and registers itself under a name.
- **Flows** combine components: `ingest`, `rag`, and `agent`. Agentic RAG is the agent flow with a `retriever_tool`.
- **Your project** is one YAML file plus prompts, custom tools, and business rules in `project/`.

You switch between plain RAG, an agent, and agentic RAG by changing config, not code.

## Quickstart

Requires Python 3.11+. The commands below use `uv`; plain `pip` works the same way.

```bash
uv venv && uv pip install -e ".[dev]"      # or: python -m venv .venv && pip install -e ".[dev]"
cp .env.example .env                        # set LLM_BASE_URL, LLM_MODEL, LLM_TOKEN, EMBED_MODEL

aikit validate --ping                       # build everything and say hello to the gateway
aikit ingest                                # index project/data
aikit ask "How many days do I have to return an item?"
aikit run "Refund order A-1001, total 80, bought 3 days ago"   # asks before issuing the refund
aikit eval                                  # run project/evals/datasets, write a JSON report
aikit serve                                 # HTTP API on :8000 (POST /runs streams SSE)
```

Everything works without a gateway: add `--offline` (or set `AIKIT_OFFLINE=1`) to swap every LLM and embedder for deterministic fakes. The test suite and CI use this mode.

```bash
aikit --offline ingest && aikit --offline eval
```

Useful global options: `-c/--config` picks a config file (default `project/app.yaml`, or `AIKIT_CONFIG`), `-s key.path=value` overrides any value, and `-v` shows structured logs.

## Starting a new app

```bash
copier copy --trust path/or/git-url/of/this/template my-new-app
cd my-new-app
```

Point Copier at a git URL or a committed clone of the template. Copier then copies only tracked files. A plain folder works too, but Copier walks every file in it, including `.venv`, which is slow.

Copier asks for a project name and the kernel package name. Keep `aikit` if teams share one kernel; choose an org-prefixed name such as `acme_ai` if this app should own its copy. Later, `copier update --trust` pulls template improvements into the app.

Then edit only `project/`:

| Path | What goes there |
|---|---|
| `project/app.yaml` | Active config; `extends` one of the profiles and overrides values |
| `project/profiles/` | `base.yaml` (shared components), `rag.yaml`, `agent.yaml`, `agentic_rag.yaml` |
| `project/prompts/` | Prompt files, versioned with the code |
| `project/tools/` | Custom tools (`@tool` functions or `BaseTool` classes) |
| `project/domain/` | Business rules the tools call; unit-test them without an LLM |
| `project/data/` | Documents to ingest (only `samples/` is committed) |
| `project/evals/datasets/` | Golden questions and agent tasks (JSONL) |

If you find yourself editing `src/aikit/` for one app, the change probably belongs in a new component, a hook, or a plugin package instead. See [docs/adding_components.md](docs/adding_components.md).

## Config in one example

```yaml
extends: project/profiles/base.yaml      # paths are relative to the repo root

imports: [project.tools]                 # modules that register custom components

components:                              # named, reusable building blocks
  llm:
    type: openai_compat
    base_url: ${LLM_BASE_URL}
    model: ${LLM_MODEL}
    api_key: ${LLM_TOKEN:-}
  retriever:
    type: hybrid
    store: "@vector_store"               # "@name" references another component
    embedder: "@embedder"

flow:
  type: agent
  llm: "@llm"
  tools:
    - type: retriever_tool
      name: search_policies
      retriever: "@retriever"
    - check_refund_eligibility           # shorthand for {type: check_refund_eligibility}
    - issue_refund
  policy:
    max_steps: 8
    max_tokens: 80000                    # write-capable tools need approval by default
```

`aikit components` lists everything registered. `aikit components --schema retriever/hybrid` shows the parameters a component accepts.

## Quality gates

```bash
poe check        # ruff, pyright, import-linter (architecture rules), pytest
poe fmt          # format and autofix
```

- `tests/contract/` holds the shared suites every adapter must pass. Add a subclass when you add a new LLM, embedder, vector store, or chunker.
- `tests/integration/` runs all three profiles end to end offline, plus the CLI and API.
- `.importlinter` enforces the layering described in [docs/architecture.md](docs/architecture.md).

## Production checklist

- Replace `get_principal` in `src/aikit/serving/api.py` with your SSO/OIDC validation. Caller groups drive document ACL filtering.
- Swap `in_memory` for a persistent vector store, and add a persistent `run_store` for paused agent runs (see [docs/adding_components.md](docs/adding_components.md)).
- Set `observability.tracing: true` with an `otlp_endpoint` (install the `otel` extra), and set `observability.costs` to your gateway's chargeback rates.
- Run `aikit eval --min-pass-rate 0.9` in CI against the real gateway before releasing prompt or model changes.

## Further reading

- Every folder has its own `README.md` describing its files and rules. Start with [src/aikit/](src/aikit/README.md), [project/](project/README.md), and [tests/](tests/README.md).
- [AGENTS.md](AGENTS.md), plus scoped `AGENTS.md` files in `src/aikit/`, `src/aikit/components/`, `project/`, and `tests/`, give AI coding assistants the layout, hard rules, and conventions. This is the tool-neutral [agents.md](https://agents.md) format, read by Cursor, Codex, Copilot, Windsurf, Zed, and others. `CLAUDE.md`, `GEMINI.md`, and `.github/copilot-instructions.md` are thin pointers to it.
- [docs/architecture.md](docs/architecture.md) covers layers, the request lifecycle, and extension points.
- [docs/adding_components.md](docs/adding_components.md) covers adding tools, adapters, plugins, and flows.
- [docs/decisions/](docs/decisions/) records the architecture decisions behind the template.
