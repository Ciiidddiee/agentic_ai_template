# aikit.serving

Entry points. These are thin layers over `runtime.load_runtime()`; no business logic lives here.

## cli.py (`aikit`)

Global options: `-c/--config` (or `AIKIT_CONFIG`), `--offline`, `-s/--set key.path=value` (repeatable), `-v/--verbose`.

| Command | Purpose |
|---|---|
| `validate [--ping]` | Build every component; `--ping` also calls the LLM and embedder |
| `components [--kind K] [--schema kind/name]` | List registered components or show a component's parameters |
| `ingest` | Run the ingest pipeline |
| `ask "question"` | One-shot query (any flow) |
| `run "task" [--auto-approve]` | Agent run with interactive approvals |
| `eval [--dataset P] [--min-pass-rate X] [--output P]` | Run eval datasets |
| `serve [--host] [--port]` | Start the HTTP API (default `127.0.0.1:8000`) |

## api.py (FastAPI)

`GET /health`, `GET /components`, `POST /ingest`, `POST /query`, `POST /runs` (SSE by default; send `stream: false` for JSON), and `POST /runs/{run_id}/approve` (`approved: true|false`, or a map of call id to decision).

`get_principal()` is a placeholder that trusts the `X-User-Id` / `X-User-Groups` headers. Replace it with real SSO/OIDC token validation before deploying, because `groups` decide which documents a caller can see.
