# docs/decisions

Architecture decision records (ADRs): short notes on why something is the way it is.

| ADR | Decision |
|---|---|
| [0001](0001-config-driven-kernel.md) | One config-driven kernel shared by RAG and agent apps |
| [0002](0002-hexagonal-boundaries.md) | Ports and adapters in the kernel; DDD only in `project/domain` |
| [0003](0003-plugins-and-factories.md) | Registry-backed factories and allowlisted entry-point plugins |
| [0004](0004-offline-fakes-and-evals.md) | Offline fakes, contract tests, and evals in every project |

## Adding one

Copy an existing ADR to `NNNN-short-title.md` with sections Context, Decision, and Consequences. Set `Status: proposed`, and change it to `accepted` once merged. Don't rewrite accepted ADRs; supersede them with a new one and link back.
