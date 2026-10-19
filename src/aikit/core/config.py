"""Loads app config.

Order: YAML -> extends -> overrides -> offline swap -> ${ENV} interpolation -> validation.

All paths inside config files (extends, prompts, data, indexes) are relative to
the working directory, which is the repo root for the CLI, API, and tests.
"""

from __future__ import annotations

import copy
import os
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from aikit.core.errors import ConfigError
from aikit.core.registry import KINDS

_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")
OFFLINE_KINDS = ("llm", "embedder")


class AppSection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = "aikit-app"
    description: str = ""


class ModelCost(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input_per_1k: float = 0.0
    output_per_1k: float = 0.0


class ObservabilitySection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    log_level: str = "INFO"
    log_format: Literal["console", "json"] = "console"
    tracing: bool = False
    otlp_endpoint: str | None = None
    service_name: str | None = None
    costs: dict[str, ModelCost] = Field(default_factory=dict)


class EvalDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    kind: Literal["rag", "agent"] | None = None


class EvalSection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    datasets: list[EvalDataset] = Field(default_factory=list)
    judge: str | None = Field(default=None, description="Component reference, e.g. '@llm'")
    auto_approve: bool = False
    output_dir: str = ".aikit/evals"


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app: AppSection = Field(default_factory=AppSection)
    imports: list[str] = Field(
        default_factory=list, description="Modules to import so they can register components"
    )
    plugins: list[str] = Field(
        default_factory=list, description="Allowlisted entry-point plugins to load"
    )
    components: dict[str, dict[str, Any]] = Field(default_factory=dict)
    ingest: dict[str, Any] | None = None
    flow: dict[str, Any]
    observability: ObservabilitySection = Field(default_factory=ObservabilitySection)
    evals: EvalSection = Field(default_factory=EvalSection)


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Merge `override` into `base`.

    Mappings merge recursively, except when both sides have a different `type`:
    then the override replaces the whole spec, so swapping a component never
    leaks the old component's parameters. A `null` override removes the key.
    Lists are replaced, not concatenated.
    """
    result = copy.deepcopy(dict(base))
    for key, value in override.items():
        if value is None:
            result.pop(key, None)
            continue
        current = result.get(key)
        if isinstance(current, Mapping) and isinstance(value, Mapping):
            if "type" in current and "type" in value and current["type"] != value["type"]:
                result[key] = copy.deepcopy(dict(value))
            else:
                result[key] = deep_merge(current, value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigError(f"Config file not found: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: top level must be a mapping")
    return data


def load_raw(path: str | Path, _seen: tuple[Path, ...] = ()) -> dict[str, Any]:
    """Read a config file and resolve `extends` (a path or list of paths) recursively."""
    resolved = Path(path).resolve()
    if resolved in _seen:
        chain = " -> ".join(str(p) for p in (*_seen, resolved))
        raise ConfigError(f"Circular 'extends': {chain}")
    data = _read_yaml(Path(path))
    parents = data.pop("extends", None) or []
    if isinstance(parents, str):
        parents = [parents]
    merged: dict[str, Any] = {}
    for parent in parents:
        merged = deep_merge(merged, load_raw(parent, (*_seen, resolved)))
    return deep_merge(merged, data)


def apply_overrides(
    raw: dict[str, Any], overrides: Mapping[str, Any] | Iterable[str] | None
) -> dict[str, Any]:
    """Apply dotted-path overrides: `{"flow.top_k": 3}` or `["flow.top_k=3"]`.

    String values are parsed as YAML, so `flow.filters={tag: a}` gives a mapping.
    """
    if not overrides:
        return raw
    pairs: list[tuple[str, Any]] = []
    if isinstance(overrides, Mapping):
        pairs = list(overrides.items())
    else:
        for item in overrides:
            if "=" not in item:
                raise ConfigError(f"Override must look like key.path=value, got '{item}'")
            key, _, value = item.partition("=")
            pairs.append((key.strip(), yaml.safe_load(value)))
    result = copy.deepcopy(raw)
    for dotted, value in pairs:
        node = result
        *parents, leaf = dotted.split(".")
        for part in parents:
            child = node.get(part)
            if not isinstance(child, dict):
                child = {}
                node[part] = child
            node = child
        node[leaf] = value
    return result


def make_offline(raw: dict[str, Any]) -> dict[str, Any]:
    """Swap every LLM and embedder component for its offline fake."""
    result = copy.deepcopy(raw)
    for name, spec in (result.get("components") or {}).items():
        if not isinstance(spec, dict):
            continue
        kind = spec.get("kind") or (name if name in KINDS else None)
        if kind in OFFLINE_KINDS:
            replacement: dict[str, Any] = {"type": "fake"}
            if "kind" in spec:
                replacement["kind"] = kind
            result["components"][name] = replacement
    return result


def interpolate_env(value: Any, env: Mapping[str, str], missing: set[str]) -> Any:
    if isinstance(value, str):

        def replace(match: re.Match[str]) -> str:
            name, default = match.group(1), match.group(2)
            if name in env:
                return env[name]
            if default is not None:
                return default
            missing.add(name)
            return match.group(0)

        return _ENV_PATTERN.sub(replace, value)
    if isinstance(value, list):
        return [interpolate_env(item, env, missing) for item in value]
    if isinstance(value, dict):
        return {key: interpolate_env(item, env, missing) for key, item in value.items()}
    return value


def load_config(
    path: str | Path,
    *,
    overrides: Mapping[str, Any] | Iterable[str] | None = None,
    offline: bool = False,
    env: Mapping[str, str] | None = None,
) -> AppConfig:
    raw = apply_overrides(load_raw(path), overrides)
    if offline:
        raw = make_offline(raw)
    missing: set[str] = set()
    raw = interpolate_env(raw, os.environ if env is None else env, missing)
    if missing:
        raise ConfigError(
            "Missing environment variables (set them or add a ${VAR:-default}): "
            + ", ".join(sorted(missing))
        )
    try:
        return AppConfig.model_validate(raw)
    except ValidationError as exc:
        details = "\n".join(
            f"  {'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()
        )
        raise ConfigError(f"Invalid config {path}:\n{details}") from exc
