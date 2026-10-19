# project/evals

Evaluation data for this app, listed under `evals.datasets` in the config and run with `aikit eval` (reports go to `.aikit/evals/`).

| Path | Contents |
|---|---|
| [`datasets/`](datasets/README.md) | JSONL golden sets: one case per line |

Workflow:

1. `aikit --offline eval` checks wiring in CI, with no gateway needed.
2. `aikit eval --min-pass-rate 0.9` checks quality against the real model before prompt or model changes ship.
3. When a user reports a bad answer, add it as a case.
