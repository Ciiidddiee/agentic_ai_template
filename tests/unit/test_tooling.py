from __future__ import annotations

import pytest
from pydantic import ValidationError

from aikit.core.context import RunContext
from aikit.core.registry import registry
from aikit.core.tooling import tool


@tool(name="unit_test_add", capabilities=["read"])
def add(a: int, b: int = 2, ctx: RunContext | None = None) -> dict:
    """Add two numbers."""
    return {"sum": a + b, "user": ctx.user_id if ctx else None}


@tool(name="unit_test_async_echo", capabilities=["write"], requires_approval=True)
async def echo(text: str) -> str:
    """Echo text."""
    return text


def test_schema_comes_from_signature_and_hides_ctx() -> None:
    instance = registry.get("tool", "unit_test_add")()
    assert instance.spec.description == "Add two numbers."
    assert set(instance.spec.parameters["properties"]) == {"a", "b"}
    assert instance.spec.parameters["required"] == ["a"]
    assert instance.spec.read_only


async def test_function_tool_runs_with_context() -> None:
    instance = registry.get("tool", "unit_test_add")()
    result = await instance.run({"a": 3}, RunContext(user_id="u1"))
    assert result.data["output"] == {"sum": 5, "user": "u1"}


async def test_async_tool_and_approval_flag() -> None:
    instance = registry.get("tool", "unit_test_async_echo")()
    assert instance.spec.requires_approval
    assert not instance.spec.read_only
    result = await instance.run({"text": "hi"}, RunContext())
    assert result.content == "hi"


async def test_invalid_arguments_raise_validation_error() -> None:
    instance = registry.get("tool", "unit_test_add")()
    with pytest.raises(ValidationError):
        await instance.run({"a": "not a number"}, RunContext())
    with pytest.raises(ValidationError):
        await instance.run({"a": 1, "unexpected": 1}, RunContext())


def test_config_can_rename_and_redescribe() -> None:
    instance = registry.get("tool", "unit_test_add")(name="plus", description="Sum")
    assert instance.spec.name == "plus"
    assert instance.spec.description == "Sum"
