from __future__ import annotations

import string
from typing import Any
from urllib.parse import quote

import httpx

from aikit.core.context import RunContext
from aikit.core.registry import register
from aikit.core.tooling import BaseTool
from aikit.core.types import Capability, ToolResult, ToolSpec


@register("tool", "http")
class HttpTool(BaseTool):
    """Calls one HTTP endpoint. Path placeholders like `/tickets/{ticket_id}` become
    required string arguments; `query_params` and `body_params` add optional ones.

    GET tools are read-only. Any other method is treated as a write and needs
    approval under the default policy.
    """

    def __init__(
        self,
        name: str,
        description: str,
        base_url: str,
        path: str = "/",
        method: str = "GET",
        query_params: list[str] | None = None,
        body_params: list[str] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 10.0,
        verify: bool | str = True,
        max_chars: int = 4000,
        capabilities: list[Capability] | None = None,
        requires_approval: bool = False,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.path = path
        self.method = method.upper()
        self.query_params = query_params or []
        self.body_params = body_params or []
        self.headers = headers or {}
        self.timeout = timeout
        self.verify = verify
        self.max_chars = max_chars
        self.path_params = [f for _, f, _, _ in string.Formatter().parse(path) if f]
        self._transport: httpx.AsyncBaseTransport | None = None

        properties: dict[str, Any] = {}
        for param in self.path_params:
            properties[param] = {"type": "string"}
        for param in [*self.query_params, *self.body_params]:
            properties.setdefault(param, {"type": "string"})
        default_caps: set[Capability] = (
            {"network", "read"} if self.method == "GET" else {"network", "write"}
        )
        self.spec = ToolSpec(
            name=name,
            description=description,
            parameters={"type": "object", "properties": properties, "required": self.path_params},
            capabilities=frozenset(capabilities or default_caps),
            requires_approval=requires_approval,
        )

    async def run(self, args: dict[str, Any], ctx: RunContext) -> ToolResult:
        missing = [p for p in self.path_params if p not in args]
        if missing:
            return ToolResult(content=f"Missing arguments: {', '.join(missing)}", is_error=True)
        url = self.path.format(**{p: quote(str(args[p]), safe="") for p in self.path_params})
        query = {k: args[k] for k in self.query_params if k in args}
        body = {k: args[k] for k in self.body_params if k in args} or None
        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=self.timeout,
            verify=self.verify,
            transport=self._transport,
        ) as client:
            response = await client.request(self.method, url, params=query, json=body)
        text = response.text[: self.max_chars]
        if response.status_code >= 400:
            return ToolResult(content=f"HTTP {response.status_code}: {text}", is_error=True)
        return ToolResult(content=text, data={"status_code": response.status_code})
