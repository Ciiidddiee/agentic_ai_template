# tests/unit

Fast, isolated tests. Nothing in this folder builds a full runtime.

| File | Covers |
|---|---|
| `test_registry.py` | Registration, duplicate names, suggestions for typos, plugin allowlist |
| `test_builder.py` | `@name` refs, nested specs from annotations, parameter validation and coercion, cycles, `@@` literals |
| `test_config.py` | `extends`, merge rules, `--set` overrides, offline swap, env interpolation, unknown keys, all project profiles load |
| `test_policy.py` | Approvals, allowlists, denied capabilities, budgets |
| `test_loaders.py` | Front matter metadata; `README.md` / `AGENTS.md` excluded from ingest |
| `test_chunkers.py` | Split sizes and overlap, markdown sections, deterministic chunk ids |
| `test_tooling.py` | `@tool` schemas, hidden `ctx`, async tools, argument validation |
| `test_guardrails.py` | PII redaction, length limits, output schema |
| `test_refund_domain.py` | Example business rules in `project/domain` |
| `test_rename_package.py` | `scripts/rename_package.py` produces an importable package; skipped once a project is renamed |

Use a fresh `Registry()` with `Builder(..., target=reg)` (see `test_builder.py`) when a test registers throwaway components, so the global registry stays clean.
