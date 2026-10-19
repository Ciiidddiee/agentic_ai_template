from __future__ import annotations

from typing import Any

import pytest

from aikit.core.builder import Builder
from aikit.core.errors import ConfigError, ReferenceCycleError
from aikit.core.ports import LLM, Tool
from aikit.core.registry import Registry


class DummyLLM:
    def __init__(self, model: str = "m", temperature: float = 0.0) -> None:
        self.model = model
        self.temperature = temperature


class ChainedLLM:
    def __init__(self, llm: LLM) -> None:
        self.llm = llm


class DummyTool:
    def __init__(self, name: str = "t") -> None:
        self.name = name


class Agent:
    def __init__(self, llm: LLM, tools: list[Tool] | None = None, label: str = "") -> None:
        self.llm = llm
        self.tools = tools or []
        self.label = label


@pytest.fixture
def reg() -> Registry:
    r = Registry()
    r.add("llm", "dummy", DummyLLM)
    r.add("llm", "chained", ChainedLLM)
    r.add("tool", "dummy_tool", DummyTool)
    r.add("flow", "agent", Agent)
    return r


def test_references_are_resolved_and_cached(reg: Registry) -> None:
    builder = Builder({"llm": {"type": "dummy", "model": "big"}}, target=reg)
    flow = builder.build({"type": "agent", "llm": "@llm"}, "flow", path="flow")
    assert isinstance(flow.llm, DummyLLM)
    assert flow.llm.model == "big"
    assert builder.get("llm") is flow.llm


def test_nested_specs_use_the_annotation_kind(reg: Registry) -> None:
    builder = Builder({"llm": {"type": "dummy"}}, target=reg)
    flow = builder.build(
        {
            "type": "agent",
            "llm": "@llm",
            "tools": ["dummy_tool", {"type": "dummy_tool", "name": "x"}],
        },
        "flow",
        path="flow",
    )
    assert [t.name for t in flow.tools] == ["t", "x"]


def test_explicit_kind_for_custom_component_names(reg: Registry) -> None:
    builder = Builder({"fast": {"kind": "llm", "type": "dummy", "model": "small"}}, target=reg)
    assert builder.get("fast").model == "small"


def test_component_without_kind_is_rejected(reg: Registry) -> None:
    builder = Builder({"fast": {"type": "dummy"}}, target=reg)
    with pytest.raises(ConfigError, match="add a 'kind'"):
        builder.get("fast")


def test_parameters_are_validated(reg: Registry) -> None:
    builder = Builder({"llm": {"type": "dummy", "temperature": "hot"}}, target=reg)
    with pytest.raises(ConfigError, match=r"components\.llm\.temperature"):
        builder.get("llm")


def test_unknown_parameters_are_rejected(reg: Registry) -> None:
    builder = Builder({"llm": {"type": "dummy", "temprature": 0.2}}, target=reg)
    with pytest.raises(ConfigError, match="temprature"):
        builder.get("llm")


def test_types_are_coerced(reg: Registry) -> None:
    builder = Builder({"llm": {"type": "dummy", "temperature": "0.5"}}, target=reg)
    assert builder.get("llm").temperature == 0.5


def test_reference_cycle_detected(reg: Registry) -> None:
    builder = Builder(
        {
            "a": {"kind": "llm", "type": "chained", "llm": "@b"},
            "b": {"kind": "llm", "type": "chained", "llm": "@a"},
        },
        target=reg,
    )
    with pytest.raises(ReferenceCycleError, match="a -> b -> a"):
        builder.get("a")


def test_unknown_reference(reg: Registry) -> None:
    builder = Builder({}, target=reg)
    with pytest.raises(ConfigError, match="Unknown component reference '@nope'"):
        builder.build({"type": "agent", "llm": "@nope"}, "flow", path="flow")


def test_double_at_is_a_literal(reg: Registry) -> None:
    builder = Builder({"llm": {"type": "dummy"}}, target=reg)
    flow = builder.build({"type": "agent", "llm": "@llm", "label": "@@team"}, "flow", path="flow")
    assert flow.label == "@team"


def test_constructor_errors_become_config_errors(reg: Registry) -> None:
    class Exploding:
        def __init__(self, size: int) -> None:
            raise ValueError("size must be even")

    reg.add("llm", "exploding", Exploding)
    builder = Builder({"llm": {"type": "exploding", "size": 3}}, target=reg)
    with pytest.raises(ConfigError, match="size must be even"):
        builder.get("llm")


def test_kwargs_factories_accept_extra_params(reg: Registry) -> None:
    def factory(**options: Any) -> dict[str, Any]:
        return options

    reg.add("llm", "kw", factory)
    builder = Builder({"llm": {"type": "kw", "anything": 1}}, target=reg)
    assert builder.get("llm") == {"anything": 1}
