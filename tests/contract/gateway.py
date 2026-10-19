"""A tiny in-process stand-in for an OpenAI-compatible gateway, served via httpx.MockTransport."""

from __future__ import annotations

import json
from typing import Any

import httpx

from aikit.components.embeddings.fake import FakeEmbedder


class MockGateway:
    def __init__(self, fail_first: int = 0, fail_status: int = 503) -> None:
        self.requests: list[dict[str, Any]] = []
        self.headers: list[httpx.Headers] = []
        self.fail_first = fail_first
        self.fail_status = fail_status
        self._embedder = FakeEmbedder(dimensions=32)

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def handle(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content or b"{}")
        self.requests.append(body)
        self.headers.append(request.headers)
        if self.fail_first > 0:
            self.fail_first -= 1
            return httpx.Response(self.fail_status, text="temporarily unavailable")
        if request.url.path.endswith("/embeddings"):
            return self._embeddings(body)
        if body.get("stream"):
            return self._stream(body)
        return self._chat(body)

    def _chat(self, body: dict[str, Any]) -> httpx.Response:
        last = body["messages"][-1]
        message: dict[str, Any] = {"role": "assistant", "content": f"echo: {last.get('content')}"}
        finish = "stop"
        if body.get("tools") and last["role"] == "user":
            tool = body["tools"][0]["function"]
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": tool["name"], "arguments": json.dumps({"sku": "1"})},
                    }
                ],
            }
            finish = "tool_calls"
        return httpx.Response(
            200,
            json={
                "model": body["model"],
                "choices": [{"index": 0, "message": message, "finish_reason": finish}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 7},
            },
        )

    def _stream(self, body: dict[str, Any]) -> httpx.Response:
        chunks = ["Hello", " from", " the gateway"]
        lines = [
            "data: " + json.dumps({"choices": [{"delta": {"content": c}}]}) + "\n\n" for c in chunks
        ]
        lines.append("data: [DONE]\n\n")
        return httpx.Response(
            200, content="".join(lines).encode(), headers={"content-type": "text/event-stream"}
        )

    def _embeddings(self, body: dict[str, Any]) -> httpx.Response:
        vectors = [self._embedder._vector(text) for text in body["input"]]
        # Reversed on purpose: clients must sort by `index`.
        data = [{"index": i, "embedding": v} for i, v in reversed(list(enumerate(vectors)))]
        return httpx.Response(200, json={"data": data, "model": body["model"]})
