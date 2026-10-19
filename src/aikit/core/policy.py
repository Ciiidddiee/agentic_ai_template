from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from aikit.core.context import RunContext
from aikit.core.errors import BudgetExceededError
from aikit.core.types import ToolSpec


class ToolDecision(StrEnum):
    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"


class Policy(BaseModel):
    """Limits enforced by flows on every run. Hooks and plugins cannot override these."""

    model_config = ConfigDict(extra="forbid")

    max_steps: int = Field(default=8, ge=1)
    max_tokens: int | None = Field(default=None, ge=1, description="Token budget per run")
    run_timeout_s: float | None = Field(default=120.0, gt=0)
    tool_timeout_s: float = Field(default=30.0, gt=0)
    max_parallel_tools: int = Field(default=4, ge=1)
    max_tool_output_chars: int = Field(default=8000, ge=100)
    allowed_tools: list[str] | None = Field(
        default=None, description="Allowlist of tool names; None allows every configured tool"
    )
    denied_capabilities: list[str] = Field(default_factory=list)
    require_approval: list[str] = Field(
        default_factory=list, description="Tool names that always need human approval"
    )
    approval_for_capabilities: list[str] = Field(
        default_factory=lambda: ["write", "code"],
        description="Tools with any of these capabilities need human approval",
    )

    def evaluate_tool(self, spec: ToolSpec) -> tuple[ToolDecision, str]:
        if self.allowed_tools is not None and spec.name not in self.allowed_tools:
            return ToolDecision.DENY, f"Tool '{spec.name}' is not on the allowlist."
        denied = set(spec.capabilities) & set(self.denied_capabilities)
        if denied:
            return (
                ToolDecision.DENY,
                f"Tool '{spec.name}' uses denied capabilities: {', '.join(sorted(denied))}.",
            )
        if (
            spec.requires_approval
            or spec.name in self.require_approval
            or set(spec.capabilities) & set(self.approval_for_capabilities)
        ):
            return ToolDecision.REQUIRE_APPROVAL, f"Tool '{spec.name}' needs human approval."
        return ToolDecision.ALLOW, ""

    def check_budget(self, ctx: RunContext) -> None:
        if self.max_tokens is not None and ctx.usage.total_tokens >= self.max_tokens:
            raise BudgetExceededError(
                f"Token budget of {self.max_tokens} exhausted ({ctx.usage.total_tokens} used)."
            )
