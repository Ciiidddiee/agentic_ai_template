# aikit

The reusable kernel shared by every RAG and agent app. Apps configure it with YAML and extend it through the registry. They should not need to edit it.

## Layout

| Path | Layer | Purpose |
|---|---|---|
| [`core/`](core/README.md) | kernel | Types, interfaces (`ports.py`), registry, builder, config, policy, hooks. No I/O dependencies. |
| [`components/`](components/README.md) | adapters | Registered implementations of the interfaces (LLMs, stores, tools, ...) |
| [`flows/`](flows/README.md) | use cases | `ingest`, `rag`, and `agent` flows built only on interfaces |
| [`observability/`](observability/README.md) | cross-cutting | Logging, tracing, cost accounting, `TelemetryHook` |
| `runtime.py` | composition root | `load_runtime()` turns config into a ready `Runtime` |
| [`evals/`](evals/README.md) | quality | Dataset runner and metrics |
| [`serving/`](serving/README.md) | entry points | Typer CLI and FastAPI app |

## Import rules (enforced by `.importlinter`)

- `core` imports nothing from the other layers, and no httpx, fastapi, typer, structlog, or OpenTelemetry.
- `components`, `flows`, and `observability` never import each other.
- Only `runtime`, `evals`, and `serving` may import across layers. `runtime` may not import `serving` or `evals`.

## Public API

`from aikit import RunContext, register, registry, BaseTool, tool, Message, RunEvent, RunResult`

## runtime.py

`load_runtime(config_path=None, overrides=(), offline=None)` does the following:

1. Loads `.env`.
2. Resolves `AIKIT_CONFIG` (default `project/app.yaml`) and `AIKIT_OFFLINE`.
3. Imports built-in components and flows, then the config's `imports:`, then allowlisted `plugins:`.
4. Builds the flow and the ingest pipeline, and attaches `TelemetryHook`.

Always `await runtime.aclose()` when done, so HTTP clients and stores shut down cleanly.
