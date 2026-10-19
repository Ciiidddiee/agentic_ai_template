from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from aikit.core.context import RunContext
from aikit.core.errors import ConfigError, GuardrailViolationError, RunNotFoundError
from aikit.core.hooks import Hook
from aikit.core.policy import Policy, ToolDecision
from aikit.core.ports import LLM, Guardrail, Memory, RunStore, Tool
from aikit.core.prompts import load_prompt
from aikit.core.registry import register
from aikit.core.runs import InMemoryRunStore
from aikit.core.types import (
    Citation,
    LLMResponse,
    Message,
    RunEvent,
    RunResult,
    RunStatus,
    ToolCall,
    ToolResult,
    ToolSpec,
    Usage,
)
from aikit.flows.base import BaseFlow, collect_result, event

DEFAULT_AGENT_PROMPT = (
    "You are a helpful assistant. Use the available tools when they help. "
    "Base factual statements on tool results and say when you don't know."
)


class AgentState(BaseModel):
    """Everything needed to pause a run for approval and resume it later."""

    run_id: str
    input: str
    messages: list[Message]
    session_id: str | None = None
    user_id: str | None = None
    groups: list[str] = Field(default_factory=list)
    step: int = 0
    usage: Usage = Field(default_factory=Usage)
    pending: list[ToolCall] = Field(default_factory=list)
    approvals: dict[str, bool] = Field(default_factory=dict)
    executed: list[ToolCall] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)


@register("flow", "agent")
class AgentFlow(BaseFlow):
    """Tool-calling loop under a Policy.

    Each step asks the LLM for either tool calls or a final answer. Tools the
    policy flags for approval pause the run (status `awaiting_approval`); call
    `resume(run_id, approvals)` to continue. Read-only tools run in parallel.
    Agentic RAG is this flow with a `retriever_tool`.
    """

    def __init__(
        self,
        llm: LLM,
        tools: list[Tool] | None = None,
        prompt: str = DEFAULT_AGENT_PROMPT,
        policy: Policy | None = None,
        memory: Memory | None = None,
        run_store: RunStore | None = None,
        llm_options: dict[str, Any] | None = None,
        guardrails: list[Guardrail] | None = None,
        hooks: list[Hook] | None = None,
    ) -> None:
        super().__init__(guardrails, hooks)
        self.llm = llm
        self.prompt = load_prompt(prompt)
        self.policy = policy or Policy()
        self.memory = memory
        self.run_store: RunStore = run_store or InMemoryRunStore()
        self.llm_options = llm_options or {}
        self.tools: dict[str, Tool] = {}
        for item in tools or []:
            if item.spec.name in self.tools:
                raise ConfigError(f"Two tools are named '{item.spec.name}'")
            self.tools[item.spec.name] = item

    # ------------------------------------------------------------------ public API

    async def pending(self, run_id: str) -> list[ToolCall] | None:
        """Tool calls waiting for approval, or None if no such paused run exists."""
        raw = await self.run_store.load(run_id)
        return AgentState.model_validate(raw).pending if raw else None

    def resume_stream(
        self, run_id: str, approvals: bool | dict[str, bool], ctx: RunContext | None = None
    ) -> AsyncIterator[RunEvent]:
        ctx = ctx or RunContext()
        ctx.run_id = run_id
        return self._guarded(self._resume_events(run_id, approvals, ctx), ctx)

    async def resume(
        self, run_id: str, approvals: bool | dict[str, bool], ctx: RunContext | None = None
    ) -> RunResult:
        return await collect_result(self.resume_stream(run_id, approvals, ctx))

    # ------------------------------------------------------------------ run loop

    async def _events(self, input: str, ctx: RunContext) -> AsyncIterator[RunEvent]:
        text = await self.hooks.on_input(input, ctx)
        if ctx.timeout_s is None:
            ctx.timeout_s = self.policy.run_timeout_s
        history = await self.memory.load(ctx.session_id) if self.memory and ctx.session_id else []
        state = AgentState(
            run_id=ctx.run_id,
            input=text,
            messages=[Message.system(self.prompt), *history, Message.user(text)],
            session_id=ctx.session_id,
            user_id=ctx.user_id,
            groups=list(ctx.groups),
            usage=ctx.usage,
        )
        async for item in self._loop(state, ctx):
            yield item

    async def _resume_events(
        self, run_id: str, approvals: bool | dict[str, bool], ctx: RunContext
    ) -> AsyncIterator[RunEvent]:
        raw = await self.run_store.load(run_id)
        if raw is None:
            raise RunNotFoundError(f"No paused run with id '{run_id}'")
        state = AgentState.model_validate(raw)
        # Tools run with the requester's identity, not the approver's.
        ctx.usage = state.usage
        ctx.session_id = state.session_id
        ctx.user_id = state.user_id
        ctx.groups = list(state.groups)
        if ctx.timeout_s is None:
            ctx.timeout_s = self.policy.run_timeout_s
        for call in state.pending:
            state.approvals[call.id] = (
                approvals if isinstance(approvals, bool) else bool(approvals.get(call.id, False))
            )
        await self.run_store.delete(run_id)
        yield event("status", resumed=True, approvals=state.approvals)
        async for item in self._loop(state, ctx):
            yield item

    async def _loop(self, state: AgentState, ctx: RunContext) -> AsyncIterator[RunEvent]:
        specs: list[ToolSpec] = [t.spec for t in self.tools.values()]
        while True:
            if state.pending:
                waiting = [
                    c
                    for c in state.pending
                    if self._decide(c)[0] is ToolDecision.REQUIRE_APPROVAL
                    and c.id not in state.approvals
                ]
                if waiting:
                    await self.run_store.save(state.run_id, state.model_dump(mode="json"))
                    yield event("approval_required", calls=[c.model_dump() for c in waiting])
                    yield self._done(self._finish(state, ctx, "awaiting_approval", pending=waiting))
                    return
                async for item in self._execute_pending(state, ctx):
                    yield item
                continue

            if state.step >= self.policy.max_steps:
                answer = "I couldn't finish within the allowed number of steps."
                yield self._done(self._finish(state, ctx, "max_steps", answer=answer))
                return
            if ctx.timed_out():
                yield self._done(self._finish(state, ctx, "timeout"))
                return
            self.policy.check_budget(ctx)

            state.step += 1
            yield event("status", step=state.step)
            messages = await self.hooks.before_llm(list(state.messages), ctx)
            response = await self._chat(messages, specs, ctx)
            ctx.usage.add(response.usage)
            response = await self.hooks.after_llm(response, ctx)

            if response.tool_calls:
                state.messages.append(Message.assistant(response.content, response.tool_calls))
                state.pending = list(response.tool_calls)
                for call in state.pending:
                    yield event("tool_call", id=call.id, name=call.name, arguments=call.arguments)
                continue

            answer = await self.hooks.on_answer(response.content or "", ctx)
            state.messages.append(Message.assistant(answer))
            if self.memory and state.session_id:
                await self.memory.save(state.session_id, state.messages)
            yield event("answer", text=answer, citations=[c.model_dump() for c in state.citations])
            yield self._done(self._finish(state, ctx, "completed", answer=answer))
            return

    async def _chat(
        self, messages: list[Message], specs: list[ToolSpec], ctx: RunContext
    ) -> LLMResponse:
        call = self.llm.chat(messages, tools=specs or None, **self.llm_options)
        remaining = ctx.remaining()
        return await (asyncio.wait_for(call, remaining) if remaining is not None else call)

    def _decide(self, call: ToolCall) -> tuple[ToolDecision, str]:
        tool = self.tools.get(call.name)
        if tool is None:
            return ToolDecision.DENY, f"Unknown tool '{call.name}'."
        return self.policy.evaluate_tool(tool.spec)

    async def _execute_pending(self, state: AgentState, ctx: RunContext) -> AsyncIterator[RunEvent]:
        calls, state.pending = state.pending, []
        results: dict[str, ToolResult] = {}
        runnable: list[ToolCall] = []
        for call in calls:
            decision, reason = self._decide(call)
            if decision is ToolDecision.DENY:
                results[call.id] = ToolResult(
                    call_id=call.id, content=f"Denied: {reason}", is_error=True
                )
            elif decision is ToolDecision.REQUIRE_APPROVAL and not state.approvals.get(call.id):
                results[call.id] = ToolResult(
                    call_id=call.id, content="Rejected by the human reviewer.", is_error=True
                )
            else:
                runnable.append(call)

        parallel = [c for c in runnable if self.tools[c.name].spec.read_only]
        sequential = [c for c in runnable if not self.tools[c.name].spec.read_only]
        semaphore = asyncio.Semaphore(self.policy.max_parallel_tools)

        async def run_limited(call: ToolCall) -> tuple[str, ToolResult]:
            async with semaphore:
                return call.id, await self._run_tool(call, ctx)

        for call_id, result in await asyncio.gather(*(run_limited(c) for c in parallel)):
            results[call_id] = result
        for call in sequential:
            results[call.id] = await self._run_tool(call, ctx)

        runnable_ids = {c.id for c in runnable}
        for call in calls:
            result = results[call.id]
            state.messages.append(Message.tool(call.id, result.content, name=call.name))
            if call.id in runnable_ids:
                state.executed.append(call)
            known = {c.chunk_id for c in state.citations}
            for raw in result.data.get("citations", []):
                citation = Citation.model_validate(raw)
                if citation.chunk_id not in known:
                    state.citations.append(citation)
                    known.add(citation.chunk_id)
            yield event(
                "tool_result",
                id=call.id,
                name=call.name,
                is_error=result.is_error,
                content=result.content[:500],
                sources=[c.get("source") for c in result.data.get("citations", [])],
            )

    async def _run_tool(self, call: ToolCall, ctx: RunContext) -> ToolResult:
        tool = self.tools[call.name]
        call = await self.hooks.before_tool(call, ctx)
        try:
            result = await asyncio.wait_for(
                tool.run(call.arguments, ctx), timeout=self.policy.tool_timeout_s
            )
        except TimeoutError:
            result = ToolResult(
                content=f"Tool timed out after {self.policy.tool_timeout_s}s.", is_error=True
            )
        except ValidationError as exc:
            problems = "; ".join(
                f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
            )
            result = ToolResult(content=f"Invalid arguments: {problems}", is_error=True)
        except Exception as exc:
            result = ToolResult(content=f"Tool failed: {type(exc).__name__}: {exc}", is_error=True)

        result = result.model_copy(
            update={
                "call_id": call.id,
                "content": result.content[: self.policy.max_tool_output_chars],
            }
        )
        try:
            return await self.hooks.after_tool(call, result, ctx)
        except GuardrailViolationError as exc:
            return ToolResult(
                call_id=call.id, content=f"Tool output blocked by guardrail: {exc}", is_error=True
            )

    def _finish(
        self,
        state: AgentState,
        ctx: RunContext,
        status: RunStatus,
        *,
        answer: str = "",
        pending: list[ToolCall] | None = None,
    ) -> RunResult:
        return self._result(
            ctx,
            status,
            answer=answer,
            citations=state.citations,
            steps=state.step,
            tool_calls=state.executed,
            pending_approvals=pending or [],
        )
