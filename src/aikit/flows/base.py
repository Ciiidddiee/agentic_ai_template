from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Sequence
from typing import Any

from aikit.core.context import RunContext
from aikit.core.errors import (
    BudgetExceededError,
    GuardrailViolationError,
    RunNotFoundError,
)
from aikit.core.hooks import GuardrailHook, Hook, HookChain
from aikit.core.ports import Guardrail
from aikit.core.types import RunEvent, RunResult, RunStatus

logger = logging.getLogger("aikit.flows")


def event(type_: Any, **data: Any) -> RunEvent:
    return RunEvent(type=type_, data=data)


class BaseFlow:
    """Shared plumbing for query flows: hook chain, event emission, error-to-status mapping."""

    def __init__(
        self, guardrails: Sequence[Guardrail] | None = None, hooks: Sequence[Hook] | None = None
    ) -> None:
        self.guardrails = list(guardrails or [])
        chain: list[Hook] = [GuardrailHook(self.guardrails)] if self.guardrails else []
        self.hooks = HookChain([*chain, *(hooks or [])])

    def add_hook(self, hook: Hook, *, first: bool = False) -> None:
        self.hooks.add(hook, first=first)

    @property
    def has_output_guardrails(self) -> bool:
        return any("output" in g.stages for g in self.guardrails)

    def _events(self, input: str, ctx: RunContext) -> AsyncIterator[RunEvent]:
        raise NotImplementedError

    def stream(self, input: str, ctx: RunContext | None = None) -> AsyncIterator[RunEvent]:
        ctx = ctx or RunContext()
        return self._guarded(self._events(input, ctx), ctx, input)

    async def run(self, input: str, ctx: RunContext | None = None) -> RunResult:
        return await collect_result(self.stream(input, ctx))

    def _result(self, ctx: RunContext, status: RunStatus, **fields: Any) -> RunResult:
        return RunResult(run_id=ctx.run_id, status=status, usage=ctx.usage.model_copy(), **fields)

    def _done(self, result: RunResult) -> RunEvent:
        return event("done", result=result.model_dump(mode="json"))

    async def _guarded(
        self, events: AsyncIterator[RunEvent], ctx: RunContext, input: str | None = None
    ) -> AsyncIterator[RunEvent]:
        async def emit(item: RunEvent) -> RunEvent:
            item.run_id = ctx.run_id
            await self.hooks.on_event(item, ctx)
            return item

        yield await emit(event("start", flow=type(self).__name__, input=input))
        failure: RunResult | None = None
        try:
            async for item in events:
                yield await emit(item)
        except RunNotFoundError:
            raise
        except GuardrailViolationError as exc:
            failure = self._result(
                ctx,
                "blocked",
                answer="Sorry, I can't help with that request.",
                metadata={"guardrail": exc.guardrail, "stage": exc.stage, "reason": str(exc)},
            )
        except BudgetExceededError as exc:
            failure = self._result(ctx, "budget_exceeded", metadata={"reason": str(exc)})
        except TimeoutError:
            failure = self._result(ctx, "timeout", metadata={"reason": "Run timed out"})
        except Exception as exc:
            logger.exception("Flow %s failed (run %s)", type(self).__name__, ctx.run_id)
            failure = self._result(ctx, "error", metadata={"error": f"{type(exc).__name__}: {exc}"})
        if failure is not None:
            yield await emit(event("error", status=failure.status, **failure.metadata))
            yield await emit(self._done(failure))


async def collect_result(events: AsyncIterator[RunEvent]) -> RunResult:
    result: dict[str, Any] | None = None
    async for item in events:
        if item.type == "done":
            result = item.data["result"]
    if result is None:
        raise RuntimeError("Flow finished without a 'done' event")
    return RunResult.model_validate(result)
