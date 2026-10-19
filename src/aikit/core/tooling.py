"""Helpers for writing tools: subclass `BaseTool`, or decorate a typed function with `@tool`."""

from __future__ import annotations

import inspect
import json
from collections.abc import Callable, Iterable
from typing import Any, get_type_hints

from pydantic import BaseModel, ConfigDict, create_model

from aikit.core.context import RunContext
from aikit.core.registry import registry
from aikit.core.types import Capability, ToolResult, ToolSpec


class BaseTool:
    """Base class for class-based tools. Set `spec` in `__init__` and implement `run`."""

    spec: ToolSpec

    async def run(self, args: dict[str, Any], ctx: RunContext) -> ToolResult:
        raise NotImplementedError


def _clean_schema(schema: dict[str, Any]) -> dict[str, Any]:
    schema.pop("title", None)
    for prop in schema.get("properties", {}).values():
        if isinstance(prop, dict):
            prop.pop("title", None)
    return schema


def _to_content(value: Any) -> tuple[str, dict[str, Any]]:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    if isinstance(value, str):
        return value, {}
    return json.dumps(value, default=str, ensure_ascii=False), {"output": value}


def tool(
    name: str | None = None,
    *,
    description: str | None = None,
    capabilities: Iterable[Capability] = ("read",),
    requires_approval: bool = False,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Turn a typed function into a registered tool.

    The JSON schema comes from the function signature, the description from the
    docstring. A parameter named `ctx` receives the RunContext and is hidden from
    the model. Sync and async functions both work.

        @tool(capabilities=["read"])
        def check_stock(sku: str) -> dict:
            "Return stock level for a SKU."
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        tool_name = name or fn.__name__
        tool_description = description or inspect.getdoc(fn) or tool_name
        hints = get_type_hints(fn)
        signature = inspect.signature(fn)
        wants_ctx = "ctx" in signature.parameters
        fields: dict[str, Any] = {}
        for param_name, param in signature.parameters.items():
            if param_name == "ctx":
                continue
            annotation = hints.get(param_name, Any)
            default = ... if param.default is inspect.Parameter.empty else param.default
            fields[param_name] = (annotation, default)
        args_model = create_model(
            f"{tool_name}_args",
            __config__=ConfigDict(extra="forbid"),
            **fields,
        )
        schema = _clean_schema(args_model.model_json_schema())
        caps = frozenset(capabilities)
        default_approval = requires_approval

        class FunctionTool(BaseTool):
            def __init__(
                self,
                name: str | None = None,
                description: str | None = None,
                requires_approval: bool | None = None,
            ) -> None:
                self.spec = ToolSpec(
                    name=name or tool_name,
                    description=description or tool_description,
                    parameters=schema,
                    capabilities=caps,
                    requires_approval=(
                        default_approval if requires_approval is None else requires_approval
                    ),
                )

            async def run(self, args: dict[str, Any], ctx: RunContext) -> ToolResult:
                validated = args_model.model_validate(args)
                kwargs = {key: getattr(validated, key) for key in fields}
                if wants_ctx:
                    kwargs["ctx"] = ctx
                output = fn(**kwargs)
                if inspect.isawaitable(output):
                    output = await output
                content, data = _to_content(output)
                return ToolResult(content=content, data=data)

        FunctionTool.__name__ = FunctionTool.__qualname__ = f"{tool_name}_tool"
        FunctionTool.__module__ = fn.__module__
        registry.add("tool", tool_name, FunctionTool)
        fn.tool_class = FunctionTool  # type: ignore[attr-defined]
        return fn

    return decorator
