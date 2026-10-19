# project/domain

Business rules as plain, typed Python, with no LLM, HTTP, or framework imports. This is the only place where DDD-style modelling (entities, value objects, domain services) is used.

| File | Contents |
|---|---|
| `refunds.py` | `RefundRequest`, `RefundDecision`, and `evaluate_refund()` (30-day window, 15% restocking fee for opened items, manager approval above $500); `RefundConfirmation` and `issue_refund()` (stub for the payments system) |

## Why it's separate

- Rules hold for every caller (agent, API, or batch job), whatever the prompt says.
- They are unit tested quickly and deterministically (`tests/unit/test_refund_domain.py`).
- Tools in `project/tools/` stay thin adapters over these functions.

Replace `refunds.py` with your own domain modules. Call real systems (ERP, CRM, payments) through small client classes, so tests can substitute fakes.
