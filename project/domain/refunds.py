"""Example domain: Acme's refund policy.

The rules live here, not in a prompt, so they are enforced the same way whether
the caller is the agent, an API, or a back-office UI, and they can be unit tested.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

RETURN_WINDOW_DAYS = 30
RESTOCKING_FEE_RATE = 0.15
MANAGER_APPROVAL_ABOVE = 500.0


class RefundRequest(BaseModel):
    order_total: float = Field(gt=0)
    days_since_purchase: int = Field(ge=0)
    opened: bool = False


class RefundDecision(BaseModel):
    eligible: bool
    refund_amount: float
    needs_manager_approval: bool
    reason: str


def evaluate_refund(request: RefundRequest) -> RefundDecision:
    if request.days_since_purchase > RETURN_WINDOW_DAYS:
        return RefundDecision(
            eligible=False,
            refund_amount=0.0,
            needs_manager_approval=False,
            reason=f"Outside the {RETURN_WINDOW_DAYS}-day return window.",
        )
    amount = request.order_total
    reason = "Within the return window; full refund."
    if request.opened:
        amount = round(amount * (1 - RESTOCKING_FEE_RATE), 2)
        reason = (
            "Within the return window; opened items carry a "
            f"{RESTOCKING_FEE_RATE:.0%} restocking fee."
        )
    return RefundDecision(
        eligible=True,
        refund_amount=amount,
        needs_manager_approval=amount > MANAGER_APPROVAL_ABOVE,
        reason=reason,
    )


class RefundConfirmation(BaseModel):
    refund_id: str
    order_id: str
    amount: float
    status: str = "issued"


def issue_refund(order_id: str, amount: float) -> RefundConfirmation:
    """Stand-in for the real payments integration."""
    if amount <= 0:
        raise ValueError("Refund amount must be positive")
    return RefundConfirmation(
        refund_id=f"rf_{uuid.uuid4().hex[:10]}", order_id=order_id, amount=amount
    )
