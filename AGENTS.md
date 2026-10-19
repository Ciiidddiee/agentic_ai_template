# AGENTS.md

Guidance for AI coding assistants working in this repository, in the open [AGENTS.md](https://agents.md) format. Humans should start with [README.md](README.md).

## Instruction files

This file applies everywhere. Folder-specific `AGENTS.md` files add rules for their subtree. Tools that support nesting load them automatically; otherwise, read the one for the folder you're editing:

| File | Scope |
|---|---|
| [src/aikit/AGENTS.md](src/aikit/AGENTS.md) | Kernel: layer rules, ports, the event contract |
| [src/aikit/components/AGENTS.md](src/aikit/components/AGENTS.md) | Writing adapters: checklist and example |
| [project/AGENTS.md](project/AGENTS.md) | App code, tools, prompts, data, YAML config |
| [tests/AGENTS.md](tests/AGENTS.md) | Test layers, fakes, fixtures |

`CLAUDE.md`, `GEMINI.md`, and `.github/copilot-instructions.md` only point here. Edit the `AGENTS.md` files, never the pointers.

## What this repo is

A reusable template for RAG and agentic AI apps on an internal OpenAI-compatible LLM gateway:

- **`src/aikit/`** is the generic kernel: interfaces, registry, config, flows, and adapters.
- **`project/`** holds one example app ("Acme Support"). New apps change `project/`, not the kernel.
- **Wiring is YAML.** `project/app.yaml` extends a profile in `project/profiles/` and names components by registry `type`, connecting them with `"@name"` references.

Each folder has a `README.md` describing its files. Read the one for the folder you're changing before you edit.

## Where things go

| Change | Location |
|---|---|
| App tool | `project/tools/<module>.py` (`@tool`), imported in `project/tools/__init__.py` |
| Business rule | `project/domain/` (pure Python; tools call it) |
| Prompt | `project/prompts/*.md`, referenced by path in config |
| Wiring, models, parameters | `project/app.yaml` or `project/profiles/*.yaml` |
| Reusable adapter | `src/aikit/components/<kind>/` with `@register(kind, name)` |
| New interface | `src/aikit/core/ports.py` + `KIND_BY_PORT` + a contract suite in `tests/contract/` |
| Cross-cutting behaviour | a `Hook` subclass registered as kind `hook` |
| New workflow shape | a `BaseFlow` subclass in `src/aikit/flows/` |

## Hard rules

1. **Respect the layers** (enforced by `lint-imports`):
   - `core` imports no other layer and no I/O libraries;
   - `components`, `flows`, and `observability` never import each other;
   - only `runtime`, `evals`, and `serving` compose layers.
2. **Never bypass `Policy`.** Tools with side effects declare `write` (or `requires_approval=True`). Don't add approval shortcuts.
3. **Enforce ACLs in the vector store** using `groups`, never by filtering afterwards.
4. **Keep business rules out of prompts.** Put them in `project/domain/`.
5. **No secrets in code or YAML.** Use `${ENV_VAR}` in config and `.env` locally.
6. **Everything must work offline.** New LLM or embedder kinds need a fake; tests must not call the network.
7. **Keep docs current** (see below).

## Keeping docs current

Every folder has a `README.md` with a table of its files. That is the map humans and assistants navigate by. When a change:

- **adds, renames, or removes a file or folder:** update that folder's `README.md`, and add a README for a new folder;
- **adds a component:** add a row to the folder README and to `src/aikit/components/README.md`;
- **changes a CLI command, config key, or event type:** update `src/aikit/serving/README.md`, `project/AGENTS.md`, or `src/aikit/flows/README.md`;
- **changes a layer rule or a core design choice:** update `docs/architecture.md` and add an ADR in `docs/decisions/`;
- **changes commands, rules, or conventions:** update the relevant `AGENTS.md`.

Keep READMEs short: purpose, a file table, and the rules for that folder. Put explanations in `docs/`.

## Commands (run from the repo root)

```bash
poe check                 # ruff + pyright + lint-imports + pytest; run before finishing
poe fmt                   # format and autofix
aikit --offline validate  # build the configured app with fakes
aikit --offline ingest && aikit --offline eval
aikit components --schema retriever/hybrid   # a component's config parameters
```

On Windows without `poe` on PATH, use `.venv\Scripts\python -m pytest`, `.venv\Scripts\ruff check .`, `.venv\Scripts\lint-imports`, and `.venv\Scripts\python -m pyright`.

## Conventions

- Python 3.11+, with `from __future__ import annotations` in every module. Fully typed: pyright runs in standard mode.
- Async I/O everywhere (`async def` on ports). Use `httpx.AsyncClient`, never `requests`.
- Pydantic models for data crossing boundaries. Dataclasses only for internal state.
- Constructor parameters are the config schema: type them precisely, give safe defaults, and avoid `**kwargs`.
- Import optional dependencies lazily, and raise `ConfigError` with an install hint if they're missing.
- Raise errors from `aikit.core.errors`. Flows map them to run statuses.
- Tests: unit tests for logic, contract tests for adapters, and integration tests through `offline_runtime`.

## Further reading

- [docs/architecture.md](docs/architecture.md)
- [docs/adding_components.md](docs/adding_components.md)
- [docs/decisions/](docs/decisions/README.md)
