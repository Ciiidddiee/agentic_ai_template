"""Domain rules are plain code, tested without any LLM."""

from __future__ import annotations

import pytest

from project.domain.refunds import RefundRequest, evaluate_refund, issue_refund


def test_within_window_full_refund() -> None:
    decision = evaluate_refund(RefundRequest(order_total=120, days_since_purchase=10))
    assert decision.eligible
    assert decision.refund_amount == 120


def test_opened_items_pay_restocking_fee() -> None:
    decision = evaluate_refund(RefundRequest(order_total=100, days_since_purchase=5, opened=True))
    assert decision.refund_amount == 85


def test_outside_window() -> None:
    assert not evaluate_refund(RefundRequest(order_total=50, days_since_purchase=31)).eligible


def test_large_refunds_need_manager() -> None:
    decision = evaluate_refund(RefundRequest(order_total=900, days_since_purchase=1))
    assert decision.needs_manager_approval


def test_issue_refund_rejects_non_positive_amounts() -> None:
    with pytest.raises(ValueError):
        issue_refund("A-1", 0)
