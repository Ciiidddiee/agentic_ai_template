"""Shared HTTP client for OpenAI-compatible gateways (chat completions and embeddings)."""

from __future__ import annotations

import asyncio
import json
import random
from collections.abc import AsyncIterator
from typing import Any

import httpx

from aikit.core.errors import LLMError

RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}


class OpenAICompatClient:
    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        headers: dict[str, str] | None,
        timeout: float,
        max_retries: int,
        retry_backoff: float,
        verify: bool | str,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self._headers = {"Content-Type": "application/json", **(headers or {})}
        if api_key:
            self._headers["Authorization"] = f"Bearer {api_key}"
        self._timeout = timeout
        self._verify = verify
        self._client: httpx.AsyncClient | None = None
        self._transport: httpx.AsyncBaseTransport | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._headers,
                timeout=self._timeout,
                verify=self._verify,
                transport=self._transport,
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _delay(self, attempt: int, response: httpx.Response | None) -> float:
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after and retry_after.replace(".", "", 1).isdigit():
                return min(float(retry_after), 30.0)
        if self.retry_backoff <= 0:
            return 0.0
        return min(self.retry_backoff * (2**attempt), 8.0) + random.uniform(0, self.retry_backoff)

    async def post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        client = self._get_client()
        last_error: str = ""
        for attempt in range(self.max_retries + 1):
            failed: httpx.Response | None = None
            try:
                response = await client.post(path, json=payload)
            except httpx.TransportError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            else:
                if response.status_code < 400:
                    try:
                        return response.json()
                    except json.JSONDecodeError as exc:
                        raise LLMError(f"Gateway returned non-JSON body: {exc}") from exc
                failed = response
                last_error = f"HTTP {response.status_code}: {response.text[:500]}"
                if response.status_code not in RETRYABLE_STATUS:
                    raise LLMError(last_error, status_code=response.status_code)
            if attempt < self.max_retries:
                await asyncio.sleep(self._delay(attempt, failed))
        raise LLMError(
            f"Request to {path} failed after {self.max_retries + 1} attempts: {last_error}"
        )

    async def stream_sse(self, path: str, payload: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        client = self._get_client()
        async with client.stream("POST", path, json=payload) as response:
            if response.status_code >= 400:
                body = (await response.aread()).decode(errors="replace")
                raise LLMError(f"HTTP {response.status_code}: {body[:500]}", response.status_code)
            async for line in response.aiter_lines():
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                data = line[len("data:") :].strip()
                if data == "[DONE]":
                    break
                try:
                    yield json.loads(data)
                except json.JSONDecodeError:
                    continue
