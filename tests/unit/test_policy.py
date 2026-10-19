from __future__ import annotations

import pytest

from aikit.core.context import RunContext
from aikit.core.errors import BudgetExceededError
from aikit.core.policy import Policy, ToolDecision
from aikit.core.types import ToolSpec, Usage


def spec(name: str = "t", caps: set[str] | None = None, approval: bool = False) -> ToolSpec:
    return ToolSpec(
        name=name,
        description="d",
        capabilities=frozenset(caps or {"read"}),  # type: ignore[arg-type]
        requires_approval=approval,
    )


def test_read_tools_are_allowed_by_default() -> None:
    assert Policy().evaluate_tool(spec())[0] is ToolDecision.ALLOW


def test_write_tools_need_approval_by_default() -> None:
    assert Policy().evaluate_tool(spec(caps={"write"}))[0] is ToolDecision.REQUIRE_APPROVAL


def test_tool_flag_and_policy_list_require_approval() -> None:
    assert Policy().evaluate_tool(spec(approval=True))[0] is ToolDecision.REQUIRE_APPROVAL
    policy = Policy(require_approval=["t"])
    assert policy.evaluate_tool(spec())[0] is ToolDecision.REQUIRE_APPROVAL


def test_allowlist_and_denied_capabilities() -> None:
    assert Policy(allowed_tools=["other"]).evaluate_tool(spec())[0] is ToolDecision.DENY
    denied = Policy(denied_capabilities=["network"]).evaluate_tool(spec(caps={"read", "network"}))
    assert denied[0] is ToolDecision.DENY
    assert "network" in denied[1]


def test_approval_can_be_disabled_for_writes() -> None:
    policy = Policy(approval_for_capabilities=[])
    assert policy.evaluate_tool(spec(caps={"write"}))[0] is ToolDecision.ALLOW


def test_budget() -> None:
    ctx = RunContext(usage=Usage(prompt_tokens=90, completion_tokens=10))
    Policy(max_tokens=101).check_budget(ctx)
    with pytest.raises(BudgetExceededError):
        Policy(max_tokens=100).check_budget(ctx)


def test_policy_rejects_unknown_fields() -> None:
    with pytest.raises(ValueError):
        Policy.model_validate({"max_stpes": 3})
