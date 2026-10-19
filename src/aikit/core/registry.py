from __future__ import annotations

import difflib
from collections.abc import Callable, Iterable
from importlib.metadata import entry_points
from typing import Any, TypeVar

from aikit.core.errors import ComponentNotFoundError, ConfigError

KINDS: tuple[str, ...] = (
    "llm",
    "embedder",
    "vector_store",
    "loader",
    "chunker",
    "retriever",
    "reranker",
    "memory",
    "tool",
    "guardrail",
    "hook",
    "run_store",
    "flow",
)

PLUGIN_GROUP_PREFIX = "aikit"
"""Entry-point groups: `aikit.<kind>` registers one class; `aikit.plugins` imports a module."""

F = TypeVar("F", bound=Callable[..., Any])


class Registry:
    def __init__(self) -> None:
        self._items: dict[str, dict[str, Callable[..., Any]]] = {kind: {} for kind in KINDS}

    def add(
        self, kind: str, name: str, factory: Callable[..., Any], *, replace: bool = False
    ) -> None:
        bucket = self._bucket(kind)
        existing = bucket.get(name)
        if existing is not None and existing is not factory and not replace:
            raise ConfigError(
                f"A {kind} named '{name}' is already registered by "
                f"{existing.__module__}.{getattr(existing, '__qualname__', existing)}"
            )
        bucket[name] = factory

    def get(self, kind: str, name: str) -> Callable[..., Any]:
        bucket = self._bucket(kind)
        if name in bucket:
            return bucket[name]
        hint = difflib.get_close_matches(name, list(bucket), n=1)
        suggestion = f" Did you mean '{hint[0]}'?" if hint else ""
        available = ", ".join(sorted(bucket)) or "none"
        raise ComponentNotFoundError(
            f"No {kind} registered as '{name}'.{suggestion} Available: {available}"
        )

    def names(self, kind: str) -> list[str]:
        return sorted(self._bucket(kind))

    def kinds(self) -> tuple[str, ...]:
        return KINDS

    def _bucket(self, kind: str) -> dict[str, Callable[..., Any]]:
        if kind not in self._items:
            raise ConfigError(f"Unknown component kind '{kind}'. Known kinds: {', '.join(KINDS)}")
        return self._items[kind]


registry = Registry()


def register(kind: str, name: str | None = None, *, replace: bool = False) -> Callable[[F], F]:
    """Register a component class or factory function under `kind` and `name`."""

    def decorator(factory: F) -> F:
        registry.add(kind, name or factory.__name__, factory, replace=replace)
        return factory

    return decorator


def load_plugins(allowlist: Iterable[str], *, target: Registry | None = None) -> list[str]:
    """Load installed plugins, but only the ones whose entry-point name is allowlisted.

    Installing a package never activates it; it must also be listed under
    `plugins:` in the app config.
    """
    reg = target or registry
    allowed = set(allowlist)
    loaded: list[str] = []
    if not allowed:
        return loaded

    for ep in entry_points(group=f"{PLUGIN_GROUP_PREFIX}.plugins"):
        if ep.name in allowed:
            ep.load()
            loaded.append(ep.name)

    for kind in KINDS:
        for ep in entry_points(group=f"{PLUGIN_GROUP_PREFIX}.{kind}"):
            if ep.name not in allowed:
                continue
            obj = ep.load()
            if callable(obj) and ep.name not in reg.names(kind):
                reg.add(kind, ep.name, obj)
            loaded.append(ep.name)

    missing = allowed - set(loaded)
    if missing:
        raise ConfigError(
            f"Plugins listed in config but not installed: {', '.join(sorted(missing))}"
        )
    return loaded
