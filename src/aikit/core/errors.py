from __future__ import annotations


class AikitError(Exception):
    """Base class for every error raised by aikit."""


class ConfigError(AikitError):
    """The configuration is invalid or references something that does not exist."""


class ComponentNotFoundError(ConfigError):
    """No component is registered under the requested kind and name."""


class ReferenceCycleError(ConfigError):
    """Components reference each other in a loop."""


class PolicyViolationError(AikitError):
    """An action was blocked by the run policy."""


class ToolNotAllowedError(PolicyViolationError):
    """A tool is not on the allowlist or uses a denied capability."""


class ApprovalRequiredError(PolicyViolationError):
    """A tool call needs human approval before it can run."""

    def __init__(self, message: str, call_ids: list[str] | None = None) -> None:
        super().__init__(message)
        self.call_ids = call_ids or []


class BudgetExceededError(PolicyViolationError):
    """The run used more tokens than the policy allows."""


class GuardrailViolationError(AikitError):
    """A guardrail rejected an input, retrieved context, tool result, or output."""

    def __init__(self, message: str, guardrail: str = "", stage: str = "") -> None:
        super().__init__(message)
        self.guardrail = guardrail
        self.stage = stage


class LLMError(AikitError):
    """The LLM backend returned an error or an unusable response."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ToolError(AikitError):
    """A tool failed while running."""


class RunNotFoundError(AikitError):
    """No paused run exists with the given id."""
