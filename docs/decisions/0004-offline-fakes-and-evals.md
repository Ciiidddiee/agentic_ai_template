# 0004: Offline fakes, contract tests, and evals in every project

- Status: accepted
- Date: 2026-10-18

## Context

Tests that call the internal gateway are slow, flaky, and cost tokens, and they cannot run in CI without credentials. Without measurement, prompt and model changes regress silently.

## Decision

- Every LLM and embedder kind ships with a deterministic `fake`. `--offline` (or `AIKIT_OFFLINE=1`) swaps them in before environment interpolation, so offline runs need no secrets.
- Each interface has a shared contract suite in `tests/contract/`. A new adapter is supported once it passes, and the OpenAI-compatible adapter is tested against an in-process mock gateway.
- Eval datasets live with the project (`project/evals/datasets/`). `aikit eval` reports retrieval recall@k, citation precision, ACL leaks, keyword coverage, optional LLM-judged faithfulness, and agent tool recall, tool precision, and task success. It writes a JSON report and can fail CI with `--min-pass-rate`.

## Consequences

- The whole pipeline, including approvals and ACLs, is tested end to end in seconds.
- Offline evals check wiring, not answer quality. Quality gates must also run `aikit eval` against the real gateway before releases.
