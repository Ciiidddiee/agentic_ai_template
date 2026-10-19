from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from aikit.core import registry as registry_module
from aikit.core.errors import ComponentNotFoundError, ConfigError
from aikit.core.registry import Registry, load_plugins


class Alpha:
    pass


class Beta:
    pass


def test_add_and_get() -> None:
    reg = Registry()
    reg.add("llm", "alpha", Alpha)
    assert reg.get("llm", "alpha") is Alpha
    assert reg.names("llm") == ["alpha"]


def test_duplicate_name_rejected_unless_replace() -> None:
    reg = Registry()
    reg.add("llm", "alpha", Alpha)
    reg.add("llm", "alpha", Alpha)  # same object is idempotent
    with pytest.raises(ConfigError, match="already registered"):
        reg.add("llm", "alpha", Beta)
    reg.add("llm", "alpha", Beta, replace=True)
    assert reg.get("llm", "alpha") is Beta


def test_missing_component_suggests_close_match() -> None:
    reg = Registry()
    reg.add("retriever", "hybrid", Alpha)
    with pytest.raises(ComponentNotFoundError, match="Did you mean 'hybrid'"):
        reg.get("retriever", "hybird")


def test_unknown_kind() -> None:
    with pytest.raises(ConfigError, match="Unknown component kind"):
        Registry().add("database", "x", Alpha)


@dataclass
class FakeEntryPoint:
    name: str
    obj: Any

    def load(self) -> Any:
        return self.obj


def test_plugins_load_only_when_allowlisted(monkeypatch: pytest.MonkeyPatch) -> None:
    groups = {
        "aikit.tool": [FakeEntryPoint("jira", Alpha), FakeEntryPoint("shell", Beta)],
    }
    monkeypatch.setattr(registry_module, "entry_points", lambda group: groups.get(group, []))
    reg = Registry()

    loaded = load_plugins(["jira"], target=reg)

    assert loaded == ["jira"]
    assert reg.get("tool", "jira") is Alpha
    assert "shell" not in reg.names("tool")


def test_allowlisted_plugin_that_is_not_installed_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry_module, "entry_points", lambda group: [])
    with pytest.raises(ConfigError, match="not installed: missing"):
        load_plugins(["missing"], target=Registry())
