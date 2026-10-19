from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from aikit.core.config import ModelCost
from aikit.core.context import RunContext
from aikit.core.hooks import Hook
from aikit.core.types import LLMResponse, Message, RunEvent, ScoredChunk, ToolCall, ToolResult
from aikit.observability.logging import get_logger
from aikit.observability.tracing import Tracer
from aikit.observability.usage import estimate_cost


class TelemetryHook(Hook):
    """Logs and traces every LLM call, tool call, retrieval, and run outcome, and adds
    `cost` to the final result metadata when prices are configured."""

    def __init__(
        self, tracer: Tracer | None = None, costs: Mapping[str, ModelCost] | None = None
    ) -> None:
        self.tracer = tracer or Tracer()
        self.costs = dict(costs or {})
        self.log = get_logger("aikit.telemetry")
        self._open: dict[str, tuple[float, Any]] = {}

    def _start(self, key: str, name: str, **attributes: Any) -> None:
        self._open[key] = (time.perf_counter(), self.tracer.start(name, **attributes))

    def _stop(self, key: str, **attributes: Any) -> float:
        started, span = self._open.pop(key, (time.perf_counter(), None))
        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        if span is not None:
            span.end(duration_ms=duration_ms, **attributes)
        return duration_ms

    async def before_llm(self, messages: list[Message], ctx: RunContext) -> list[Message]:
        self._start(f"{ctx.run_id}:llm", "llm.chat", run_id=ctx.run_id, messages=len(messages))
        return messages

    async def after_llm(self, response: LLMResponse, ctx: RunContext) -> LLMResponse:
        cost = estimate_cost(response.usage, response.model, self.costs)
        if cost is not None:
            ctx.metadata["cost"] = ctx.metadata.get("cost", 0.0) + cost
        duration = self._stop(
            f"{ctx.run_id}:llm",
            model=response.model,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
        )
        self.log.info(
            "llm.call",
            run_id=ctx.run_id,
            model=response.model,
            tool_calls=len(response.tool_calls),
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            duration_ms=duration,
        )
        return response

    async def before_tool(self, call: ToolCall, ctx: RunContext) -> ToolCall:
        self._start(f"{ctx.run_id}:tool:{call.id}", f"tool.{call.name}", run_id=ctx.run_id)
        return call

    async def after_tool(self, call: ToolCall, result: ToolResult, ctx: RunContext) -> ToolResult:
        duration = self._stop(f"{ctx.run_id}:tool:{call.id}", is_error=result.is_error)
        self.log.info(
            "tool.call",
            run_id=ctx.run_id,
            tool=call.name,
            is_error=result.is_error,
            duration_ms=duration,
        )
        return result

    async def after_retrieve(
        self, query: str, chunks: list[ScoredChunk], ctx: RunContext
    ) -> list[ScoredChunk]:
        self.log.info(
            "retrieve",
            run_id=ctx.run_id,
            results=len(chunks),
            top_score=round(max((c.score for c in chunks), default=0.0), 4),
        )
        return chunks

    async def on_event(self, event: RunEvent, ctx: RunContext) -> None:
        if event.type == "start":
            self._start(f"{ctx.run_id}:run", "run", run_id=ctx.run_id, user_id=ctx.user_id)
        elif event.type == "error":
            self.log.warning("run.error", run_id=ctx.run_id, **event.data)
        elif event.type == "done":
            result = event.data.get("result", {})
            if "cost" in ctx.metadata:
                result.setdefault("metadata", {})["cost"] = round(ctx.metadata["cost"], 6)
            usage = result.get("usage", {})
            duration = self._stop(f"{ctx.run_id}:run", status=result.get("status"))
            self.log.info(
                "run.done",
                run_id=ctx.run_id,
                status=result.get("status"),
                steps=result.get("steps"),
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
                cost=ctx.metadata.get("cost"),
                duration_ms=duration,
            )
