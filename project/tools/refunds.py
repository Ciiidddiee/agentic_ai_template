from __future__ import annotations

from aikit import RunContext, tool
from project.domain.refunds import RefundRequest, evaluate_refund
from project.domain.refunds import issue_refund as issue_refund_in_payments


@tool(capabilities=["read"])
def check_refund_eligibility(
    order_total: float, days_since_purchase: int, opened: bool = False
) -> dict:
    """Check whether an order can be refunded under the Acme refund policy and for how much."""
    decision = evaluate_refund(
        RefundRequest(
            order_total=order_total, days_since_purchase=days_since_purchase, opened=opened
        )
    )
    return decision.model_dump()


@tool(capabilities=["write"], requires_approval=True)
def issue_refund(order_id: str, amount: float, ctx: RunContext) -> dict:
    """Issue a refund to the customer's original payment method. Requires human approval."""
    confirmation = issue_refund_in_payments(order_id=order_id, amount=amount)
    return {**confirmation.model_dump(), "requested_by": ctx.user_id}
