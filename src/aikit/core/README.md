# aikit.core

The stable kernel. Everything else depends on it, and it depends on nothing but the standard library, pydantic, and PyYAML. Treat changes here as API changes.

| File | What it defines |
|---|---|
| `types.py` | Pydantic data models: `Message`, `ToolCall`, `LLMResponse`, `Usage`, `ToolSpec`, `ToolResult`, `Document`, `Chunk`, `ScoredChunk`, `Citation`, `RunEvent`, `RunResult`, `IngestReport` |
| `ports.py` | `Protocol` interfaces: `LLM`, `Embedder`, `VectorStore` (+ optional `KeywordSearchable`), `Loader`, `Chunker`, `Retriever`, `Reranker`, `Memory`, `Tool`, `Guardrail`, `RunStore`, `QueryFlow`. `KIND_BY_PORT` maps each to a registry kind. |
| `registry.py` | `KINDS`, `Registry`, the global `registry`, `@register(kind, name)`, `load_plugins()` (entry points `aikit.<kind>` / `aikit.plugins`, allowlist only) |
| `builder.py` | `Builder`: turns component specs into objects; resolves `"@name"` refs, nested specs (from constructor annotations), validates params with a model generated from the signature |
| `config.py` | `AppConfig` schema and `load_config()`: `extends` → `--set` overrides → offline fakes → `${ENV:-default}` → validation |
| `context.py` | `RunContext`: run/session/user ids, `groups` (for ACLs), usage, timeout |
| `policy.py` | `Policy` and `ToolDecision`: step/token/time limits, tool allowlist, denied capabilities, approvals |
| `hooks.py` | `Hook` base class, `GuardrailHook`, `HookChain` |
| `tooling.py` | `BaseTool` and the `@tool` decorator (schema from type hints, `ctx` hidden from the model) |
| `filters.py` | `matches_filters()` and `acl_allows()` used by stores |
| `prompts.py` | `load_prompt()` (file path or inline text) and `render()` |
| `runs.py` | `InMemoryRunStore` for paused agent runs |
| `errors.py` | `AikitError` hierarchy (`ConfigError`, `PolicyViolationError`, `GuardrailViolationError`, `LLMError`, ...) |

## Rules

- Do not add I/O libraries or vendor SDKs here. Use an adapter in `components/` instead.
- New interfaces go in `ports.py` as `@runtime_checkable` Protocols, with an entry in `KIND_BY_PORT` and a contract suite in `tests/contract/`.
- Keep `Policy` enforcement in flows, not in hooks, so plugins cannot bypass it.
