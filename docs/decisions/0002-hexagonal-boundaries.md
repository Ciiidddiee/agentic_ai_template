# 0002: Hexagonal boundaries, with DDD only in project/domain

- Status: accepted
- Date: 2026-10-18

## Context

We considered applying Domain-Driven Design to the whole template. The platform's own domain (runs, steps, tool calls, policies) is small and stable, while each app's business domain (refunds, claims, tickets) is where the complexity lives.

## Decision

- The kernel uses ports and adapters: `core/ports.py` defines `Protocol` interfaces; `components/` holds adapters; flows depend only on ports.
- `import-linter` enforces the boundaries in CI (see `.importlinter`).
- Tactical DDD (entities, value objects, domain services) is used only inside `project/domain/`. Tools are thin wrappers that call domain code, so business rules hold whether the caller is the agent, an API, or a person.
- Prompts never encode business rules that must hold; they only guide the model toward the right tools.

## Consequences

- Vendors, vector stores, and frameworks can be swapped without touching flows or business logic.
- Domain logic is unit tested without an LLM (see `tests/unit/test_refund_domain.py`).
- There is a little more indirection than calling an SDK directly. That is deliberate.
