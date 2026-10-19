"""Middleware around LLM calls, tool calls, and retrieval.

Hooks observe or transform data; they cannot bypass the policy, which flows
enforce directly.
"""

from __future__ import annotations

from collections.abc import Sequence

from aikit.core.context import RunContext
from aikit.core.ports import Guardrail
from aikit.core.types import LLMResponse, Message, RunEvent, ScoredChunk, ToolCall, ToolResult


class Hook:
    """Base class: override only what you need. Each method returns the value, possibly changed."""

    async def on_input(self, text: str, ctx: RunContext) -> str:
        return text

    async def before_llm(self, messages: list[Message], ctx: RunContext) -> list[Message]:
        return messages

    async def after_llm(self, response: LLMResponse, ctx: RunContext) -> LLMResponse:
        return response

    async def before_tool(self, call: ToolCall, ctx: RunContext) -> ToolCall:
        return call

    async def after_tool(self, call: ToolCall, result: ToolResult, ctx: RunContext) -> ToolResult:
        return result

    async def after_retrieve(
        self, query: str, chunks: list[ScoredChunk], ctx: RunContext
    ) -> list[ScoredChunk]:
        return chunks

    async def on_answer(self, text: str, ctx: RunContext) -> str:
        return text

    async def on_event(self, event: RunEvent, ctx: RunContext) -> None:
        return None


class GuardrailHook(Hook):
    """Applies guardrails at the input, context, tool_result, and output stages."""

    def __init__(self, guardrails: Sequence[Guardrail]) -> None:
        self.guardrails = list(guardrails)

    def has_stage(self, stage: str) -> bool:
        return any(stage in g.stages for g in self.guardrails)

    async def _apply(self, stage: str, text: str, ctx: RunContext) -> str:
        for guardrail in self.guardrails:
            if stage in guardrail.stages:
                text = await guardrail.apply(text, stage=stage, ctx=ctx)
        return text

    async def on_input(self, text: str, ctx: RunContext) -> str:
        return await self._apply("input", text, ctx)

    async def after_retrieve(
        self, query: str, chunks: list[ScoredChunk], ctx: RunContext
    ) -> list[ScoredChunk]:
        if not self.has_stage("context"):
            return chunks
        cleaned: list[ScoredChunk] = []
        for item in chunks:
            text = await self._apply("context", item.chunk.text, ctx)
            cleaned.append(
                item.model_copy(update={"chunk": item.chunk.model_copy(update={"text": text})})
            )
        return cleaned

    async def after_tool(self, call: ToolCall, result: ToolResult, ctx: RunContext) -> ToolResult:
        if not self.has_stage("tool_result"):
            return result
        return result.model_copy(
            update={"content": await self._apply("tool_result", result.content, ctx)}
        )

    async def on_answer(self, text: str, ctx: RunContext) -> str:
        return await self._apply("output", text, ctx)


class HookChain:
    """Runs hooks in order; each receives the previous hook's output."""

    def __init__(self, hooks: Sequence[Hook] = ()) -> None:
        self.hooks: list[Hook] = list(hooks)

    def add(self, hook: Hook, *, first: bool = False) -> None:
        if first:
            self.hooks.insert(0, hook)
        else:
            self.hooks.append(hook)

    async def on_input(self, text: str, ctx: RunContext) -> str:
        for hook in self.hooks:
            text = await hook.on_input(text, ctx)
        return text

    async def before_llm(self, messages: list[Message], ctx: RunContext) -> list[Message]:
        for hook in self.hooks:
            messages = await hook.before_llm(messages, ctx)
        return messages

    async def after_llm(self, response: LLMResponse, ctx: RunContext) -> LLMResponse:
        for hook in self.hooks:
            response = await hook.after_llm(response, ctx)
        return response

    async def before_tool(self, call: ToolCall, ctx: RunContext) -> ToolCall:
        for hook in self.hooks:
            call = await hook.before_tool(call, ctx)
        return call

    async def after_tool(self, call: ToolCall, result: ToolResult, ctx: RunContext) -> ToolResult:
        for hook in self.hooks:
            result = await hook.after_tool(call, result, ctx)
        return result

    async def after_retrieve(
        self, query: str, chunks: list[ScoredChunk], ctx: RunContext
    ) -> list[ScoredChunk]:
        for hook in self.hooks:
            chunks = await hook.after_retrieve(query, chunks, ctx)
        return chunks

    async def on_answer(self, text: str, ctx: RunContext) -> str:
        for hook in self.hooks:
            text = await hook.on_answer(text, ctx)
        return text

    async def on_event(self, event: RunEvent, ctx: RunContext) -> None:
        for hook in self.hooks:
            await hook.on_event(event, ctx)
