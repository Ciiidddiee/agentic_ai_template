from __future__ import annotations

import re
from collections import deque
from collections.abc import AsyncIterator
from typing import Any

from aikit.components._text import tokenize
from aikit.core.registry import register
from aikit.core.types import LLMResponse, Message, ToolCall, ToolSpec, Usage

_PASSAGE = re.compile(r"\[(\d+)\][^\n]*\n(.+?)(?=\n\s*\[\d+\]|\n\s*\nQuestion:|\Z)", re.DOTALL)
_NUMBER = re.compile(r"(?<![\w-])\d+(?:\.\d+)?")
JSON_MARKER = "Respond with JSON"


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


@register("llm", "fake")
class FakeLLM:
    """Deterministic offline LLM for tests, evals, and demos without a gateway.

    With `responses`, it replays them in order (a string is a text answer; a dict
    may contain `content` and/or `tool_calls: [{name, arguments}]`). Without a
    script it behaves heuristically: it calls the tool that best matches the
    question, summarises tool results, and answers RAG prompts by quoting the
    first context passage with a citation.
    """

    def __init__(
        self, responses: list[str | dict[str, Any]] | None = None, model: str = "fake-llm"
    ) -> None:
        self.model = model
        self._script: deque[str | dict[str, Any]] = deque(responses or [])
        self.calls: list[list[Message]] = []

    async def chat(
        self, messages: list[Message], *, tools: list[ToolSpec] | None = None, **options: Any
    ) -> LLMResponse:
        self.calls.append(list(messages))
        if self._script:
            content, tool_calls = self._from_script(self._script.popleft())
        else:
            content, tool_calls = self._heuristic(messages, tools or [])
        prompt_tokens = sum(_estimate_tokens(m.content or "") for m in messages)
        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=_estimate_tokens(content or "") if content else 1,
            ),
            model=self.model,
            finish_reason="tool_calls" if tool_calls else "stop",
        )

    async def stream(self, messages: list[Message], **options: Any) -> AsyncIterator[str]:
        response = await self.chat(messages, **options)
        words = (response.content or "").split(" ")
        for i, word in enumerate(words):
            yield word if i == len(words) - 1 else word + " "

    @staticmethod
    def _from_script(item: str | dict[str, Any]) -> tuple[str | None, list[ToolCall]]:
        if isinstance(item, str):
            return item, []
        calls = [ToolCall(**call) for call in item.get("tool_calls", [])]
        return item.get("content"), calls

    def _heuristic(
        self, messages: list[Message], tools: list[ToolSpec]
    ) -> tuple[str | None, list[ToolCall]]:
        if any(m.role == "system" and JSON_MARKER in (m.content or "") for m in messages):
            return "{}", []

        last_user = max((i for i, m in enumerate(messages) if m.role == "user"), default=-1)
        question = (messages[last_user].content or "") if last_user >= 0 else ""
        tool_messages = [m for m in messages[last_user + 1 :] if m.role == "tool"]

        if tools and not tool_messages:
            best = self._best_tool(question, tools)
            if best is not None:
                return None, [ToolCall(name=best.name, arguments=self._arguments(best, question))]

        if tool_messages:
            summary = " | ".join((m.content or "")[:300] for m in tool_messages)
            return f"Based on the tool results: {summary}", []

        for message in reversed(messages):
            match = _PASSAGE.search(message.content or "") if message.role == "user" else None
            if match:
                body = " ".join(
                    line
                    for line in match.group(2).splitlines()
                    if not line.lstrip().startswith("#")
                ).strip()
                sentence = re.split(r"(?<=[.!?])\s", body, maxsplit=1)[0]
                return f"{sentence} [{match.group(1)}]", []

        return f"(fake answer) {question}".strip(), []

    @staticmethod
    def _best_tool(question: str, tools: list[ToolSpec]) -> ToolSpec | None:
        """Score tools by word overlap; search-style tools (a `query` parameter) get a
        bonus when the input is phrased as a question."""
        words = set(tokenize(question))
        is_question = "?" in question
        best: ToolSpec | None = None
        best_score = 0
        for spec in tools:
            name_score = 2 * len(words & set(tokenize(spec.name.replace("_", " "))))
            description_score = len(words & set(tokenize(spec.description)))
            searchable = "query" in spec.parameters.get("properties", {})
            score = name_score + description_score + (2 if searchable and is_question else 0)
            if score > best_score:
                best, best_score = spec, score
        return best

    @staticmethod
    def _arguments(spec: ToolSpec, question: str) -> dict[str, Any]:
        numbers = [float(n) for n in _NUMBER.findall(question)]
        properties: dict[str, Any] = spec.parameters.get("properties", {})
        required = set(spec.parameters.get("required", properties))
        args: dict[str, Any] = {}
        for name, schema in properties.items():
            if name not in required:
                continue
            kind = schema.get("type")
            if "enum" in schema:
                args[name] = schema["enum"][0]
            elif kind == "integer":
                args[name] = int(numbers.pop(0)) if numbers else 0
            elif kind == "number":
                args[name] = numbers.pop(0) if numbers else 0.0
            elif kind == "boolean":
                args[name] = False
            else:
                args[name] = question
        return args
