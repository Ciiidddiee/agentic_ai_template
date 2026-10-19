from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from aikit.components._openai_http import OpenAICompatClient
from aikit.core.errors import LLMError
from aikit.core.registry import register
from aikit.core.types import LLMResponse, Message, ToolCall, ToolSpec, Usage


def to_openai_message(message: Message) -> dict[str, Any]:
    payload: dict[str, Any] = {"role": message.role, "content": message.content}
    if message.tool_calls:
        payload["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
            }
            for call in message.tool_calls
        ]
    if message.role == "tool":
        payload["tool_call_id"] = message.tool_call_id
    elif message.name:
        payload["name"] = message.name
    return payload


def to_openai_tool(spec: ToolSpec) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": spec.name,
            "description": spec.description,
            "parameters": spec.parameters,
        },
    }


def parse_tool_calls(raw_calls: list[dict[str, Any]] | None) -> list[ToolCall]:
    calls: list[ToolCall] = []
    for raw in raw_calls or []:
        function = raw.get("function") or {}
        arguments = function.get("arguments") or "{}"
        if isinstance(arguments, str):
            try:
                parsed = json.loads(arguments) if arguments.strip() else {}
            except json.JSONDecodeError:
                parsed = {"__invalid_json__": arguments}
        else:
            parsed = arguments
        if not isinstance(parsed, dict):
            parsed = {"value": parsed}
        call_kwargs: dict[str, Any] = {"name": function.get("name", ""), "arguments": parsed}
        if raw.get("id"):
            call_kwargs["id"] = raw["id"]
        calls.append(ToolCall(**call_kwargs))
    return calls


@register("llm", "openai_compat")
class OpenAICompatLLM:
    """Chat model behind any OpenAI-compatible gateway (vLLM, TGI, LiteLLM, Azure proxy, ...).

    `base_url` must include the version prefix, e.g. https://llm.internal/v1.
    """

    def __init__(
        self,
        model: str,
        base_url: str,
        api_key: str | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 60.0,
        max_retries: int = 3,
        retry_backoff: float = 0.5,
        verify: bool | str = True,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream_usage: bool = False,
        extra_body: dict[str, Any] | None = None,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.stream_usage = stream_usage
        self.extra_body = extra_body or {}
        self.http = OpenAICompatClient(
            base_url=base_url,
            api_key=api_key or None,
            headers=headers,
            timeout=timeout,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
            verify=verify,
        )

    def _payload(
        self, messages: list[Message], tools: list[ToolSpec] | None, options: dict[str, Any]
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [to_openai_message(m) for m in messages],
            **self.extra_body,
        }
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
        if tools:
            payload["tools"] = [to_openai_tool(t) for t in tools]
        payload.update(options)
        return payload

    async def chat(
        self, messages: list[Message], *, tools: list[ToolSpec] | None = None, **options: Any
    ) -> LLMResponse:
        data = await self.http.post_json(
            "/chat/completions", self._payload(messages, tools, options)
        )
        choices = data.get("choices") or []
        if not choices:
            raise LLMError(f"Gateway response has no choices: {str(data)[:300]}")
        message = choices[0].get("message") or {}
        usage = data.get("usage") or {}
        return LLMResponse(
            content=message.get("content"),
            tool_calls=parse_tool_calls(message.get("tool_calls")),
            usage=Usage(
                prompt_tokens=usage.get("prompt_tokens", 0) or 0,
                completion_tokens=usage.get("completion_tokens", 0) or 0,
            ),
            model=data.get("model", self.model),
            finish_reason=choices[0].get("finish_reason"),
        )

    async def stream(self, messages: list[Message], **options: Any) -> AsyncIterator[str]:
        payload = self._payload(messages, None, options)
        payload["stream"] = True
        if self.stream_usage:
            payload["stream_options"] = {"include_usage": True}
        async for event in self.http.stream_sse("/chat/completions", payload):
            for choice in event.get("choices") or []:
                delta = (choice.get("delta") or {}).get("content")
                if delta:
                    yield delta

    async def aclose(self) -> None:
        await self.http.aclose()
