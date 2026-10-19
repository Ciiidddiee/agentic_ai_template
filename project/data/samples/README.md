# project/data/samples

Example documents for the Acme Support app. The tests and `project/evals/datasets/` depend on their content: if you edit them, update the eval cases too.

| File | Access | Used to test |
|---|---|---|
| `refund_policy.md` | public | 30-day window, 15% restocking fee, manager approval above $500 |
| `shipping.md` | public | Retrieval across documents |
| `warranty.md` | public | Retrieval across documents |
| `internal_escalation.md` | `acl: [support_leads]` | ACL filtering: hidden from callers without the group |

This file is skipped during ingest.
