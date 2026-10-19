# aikit.observability

Logging, tracing, and cost accounting. Configured by the `observability:` section of the app config.

| File | Contents |
|---|---|
| `logging.py` | `configure_logging()`: structlog output to stderr, `console` or `json` format |
| `tracing.py` | `Tracer`: OpenTelemetry spans when `tracing: true` and the `otel` extra is installed; otherwise a no-op |
| `usage.py` | `estimate_cost()` from `observability.costs` (per-model `input_per_1k` / `output_per_1k`, with a `default`) |
| `telemetry.py` | `TelemetryHook`: logs and traces every LLM call, tool call, and retrieval, and adds token usage and `cost` to `RunResult.metadata` |

The runtime always adds `TelemetryHook` as the first hook.

Never log raw prompts or documents at INFO level: they can contain PII. Log ids, counts, and durations instead.
