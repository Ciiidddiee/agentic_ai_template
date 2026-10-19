"""Turns config specs into live objects using the registry.

A spec is a mapping with a `type` key plus constructor arguments:

    retriever:
      type: hybrid
      store: "@vector_store"     # reference to another named component
      embedder: "@embedder"
      top_k: 8

Nested specs are built automatically when the constructor parameter is typed
with a port (for example `tools: list[Tool]`), so the builder always knows
which kind to look up. Strings starting with `@@` are literal `@` strings.
"""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable, Mapping
from typing import Any, get_args, get_type_hints

from pydantic import BaseModel, ConfigDict, ValidationError, create_model

from aikit.core.errors import ConfigError, ReferenceCycleError
from aikit.core.hooks import Hook
from aikit.core.ports import KIND_BY_PORT
from aikit.core.registry import KINDS, Registry, registry

REF_PREFIX = "@"

_KIND_BY_TYPE: dict[type, str] = {**KIND_BY_PORT, Hook: "hook"}


def _target(factory: Callable[..., Any]) -> Callable[..., Any]:
    return factory.__init__ if isinstance(factory, type) else factory


@functools.cache
def param_hints(factory: Callable[..., Any]) -> dict[str, Any]:
    """Resolved type hints of the factory's constructor parameters."""
    try:
        return get_type_hints(_target(factory))
    except Exception:
        return {}


def kind_for_annotation(annotation: Any) -> str | None:
    """Return the component kind an annotation refers to, looking through Optional/list/etc."""
    if annotation is None:
        return None
    if isinstance(annotation, type) and annotation in _KIND_BY_TYPE:
        return _KIND_BY_TYPE[annotation]
    for arg in get_args(annotation):
        kind = kind_for_annotation(arg)
        if kind:
            return kind
    return None


def _validatable(annotation: Any) -> Any:
    """Component-typed parameters are already built objects; skip pydantic validation for them."""
    if kind_for_annotation(annotation) is not None:
        return Any
    return annotation


@functools.cache
def signature_model(factory: Callable[..., Any]) -> type[BaseModel]:
    """A pydantic model mirroring the factory's constructor, used to validate config params."""
    signature = inspect.signature(_target(factory))
    hints = param_hints(factory)
    fields: dict[str, Any] = {}
    accepts_kwargs = False
    for name, param in signature.parameters.items():
        if name == "self" or name.startswith("_"):
            continue
        if param.kind is inspect.Parameter.VAR_KEYWORD:
            accepts_kwargs = True
            continue
        if param.kind is inspect.Parameter.VAR_POSITIONAL:
            continue
        annotation = _validatable(hints.get(name, Any))
        default = ... if param.default is inspect.Parameter.empty else param.default
        fields[name] = (annotation, default)
    return create_model(
        f"{getattr(factory, '__name__', 'Component')}Params",
        __config__=ConfigDict(
            extra="allow" if accepts_kwargs else "forbid", arbitrary_types_allowed=True
        ),
        **fields,
    )


def _format_validation_error(path: str, error: ValidationError) -> str:
    lines = []
    for item in error.errors():
        loc = ".".join(str(part) for part in item["loc"])
        lines.append(f"  {path}.{loc}: {item['msg']}")
    return "\n".join(lines)


class Builder:
    """Builds named components lazily and caches them, detecting reference cycles."""

    def __init__(
        self, specs: Mapping[str, Mapping[str, Any]], *, target: Registry | None = None
    ) -> None:
        self._specs = dict(specs)
        self._registry = target or registry
        self._built: dict[str, Any] = {}
        self._stack: list[str] = []

    @property
    def built(self) -> dict[str, Any]:
        return dict(self._built)

    def names(self) -> list[str]:
        return list(self._specs)

    def kind_of(self, name: str) -> str:
        spec = self._specs[name]
        kind = spec.get("kind") or (name if name in KINDS else None)
        if not kind:
            raise ConfigError(
                f"components.{name}: add a 'kind' (one of {', '.join(KINDS)}) "
                "or name the component after its kind"
            )
        return str(kind)

    def get(self, name: str) -> Any:
        if name in self._built:
            return self._built[name]
        if name not in self._specs:
            available = ", ".join(self._specs) or "none"
            raise ConfigError(f"Unknown component reference '@{name}'. Defined: {available}")
        if name in self._stack:
            raise ReferenceCycleError(
                "Component reference cycle: " + " -> ".join([*self._stack, name])
            )
        self._stack.append(name)
        try:
            spec = {k: v for k, v in self._specs[name].items() if k != "kind"}
            obj = self.build(spec, self.kind_of(name), path=f"components.{name}")
        finally:
            self._stack.pop()
        self._built[name] = obj
        return obj

    def build_all(self) -> dict[str, Any]:
        for name in self._specs:
            self.get(name)
        return self.built

    def build(self, spec: Any, kind: str, *, path: str) -> Any:
        if isinstance(spec, str):
            if spec.startswith(REF_PREFIX) and not spec.startswith(REF_PREFIX * 2):
                return self.get(spec[1:])
            spec = {"type": spec}
        if not isinstance(spec, Mapping):
            raise ConfigError(f"{path}: expected a mapping with a 'type' key, got {spec!r}")
        params = dict(spec)
        params.pop("kind", None)
        type_name = params.pop("type", None)
        if not type_name:
            raise ConfigError(f"{path}: missing 'type' (available: {self._registry.names(kind)})")
        try:
            factory = self._registry.get(kind, str(type_name))
        except ConfigError as exc:
            raise ConfigError(f"{path}: {exc}") from exc
        return self.instantiate(factory, params, path=path)

    def instantiate(
        self, factory: Callable[..., Any], params: Mapping[str, Any], *, path: str
    ) -> Any:
        hints = param_hints(factory)
        resolved = {
            key: self._resolve(value, kind_for_annotation(hints.get(key)), f"{path}.{key}")
            for key, value in params.items()
        }
        model = signature_model(factory)
        try:
            validated = model.model_validate(resolved)
        except ValidationError as exc:
            raise ConfigError(
                f"Invalid parameters for {path}:\n{_format_validation_error(path, exc)}"
            ) from exc
        kwargs = {name: getattr(validated, name) for name in model.model_fields}
        kwargs.update(validated.model_extra or {})
        try:
            return factory(**kwargs)
        except ConfigError:
            raise
        except Exception as exc:
            raise ConfigError(f"{path}: failed to construct: {exc}") from exc

    def _resolve(self, value: Any, kind: str | None, path: str) -> Any:
        if isinstance(value, str):
            if value.startswith(REF_PREFIX * 2):
                return value[1:]
            if value.startswith(REF_PREFIX):
                return self.get(value[1:])
            return self.build(value, kind, path=path) if kind else value
        if isinstance(value, list):
            return [self._resolve(item, kind, f"{path}[{i}]") for i, item in enumerate(value)]
        if isinstance(value, Mapping):
            if kind and "type" in value:
                return self.build(value, kind, path=path)
            return {k: self._resolve(v, None, f"{path}.{k}") for k, v in value.items()}
        return value
