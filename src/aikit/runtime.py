"""Composition root: the only place where config becomes live objects."""

from __future__ import annotations

import importlib
import os
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

import aikit.components
import aikit.flows  # noqa: F401  (registers built-in flows)
from aikit.core.builder import Builder
from aikit.core.config import AppConfig, load_config
from aikit.core.errors import ConfigError
from aikit.core.ports import QueryFlow
from aikit.core.registry import load_plugins
from aikit.flows.ingest import IngestFlow
from aikit.observability import TelemetryHook, Tracer, configure_logging

DEFAULT_CONFIG = "project/app.yaml"


@dataclass
class Runtime:
    config: AppConfig
    builder: Builder
    flow: QueryFlow
    ingest: IngestFlow | None
    tracer: Tracer

    def component(self, name: str) -> Any:
        return self.builder.get(name)

    async def aclose(self) -> None:
        for obj in self.builder.built.values():
            close = getattr(obj, "aclose", None)
            if close is not None:
                await close()


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _import_project_modules(modules: Iterable[str]) -> None:
    cwd = str(Path.cwd())
    if cwd not in sys.path:
        sys.path.insert(0, cwd)
    for name in modules:
        try:
            importlib.import_module(name)
        except ImportError as exc:
            raise ConfigError(f"Cannot import '{name}' listed under imports: {exc}") from exc


def _ingest_spec(config: AppConfig) -> dict[str, Any] | None:
    if config.ingest is None:
        return None
    spec = dict(config.ingest)
    spec.setdefault("type", "ingest")
    for param, component in (("embedder", "embedder"), ("store", "vector_store")):
        if param not in spec and component in config.components:
            spec[param] = f"@{component}"
    return spec


def load_runtime(
    config_path: str | Path | None = None,
    *,
    overrides: Mapping[str, Any] | Iterable[str] | None = None,
    offline: bool | None = None,
    log_level: str | None = None,
    env_file: str | Path | None = ".env",
) -> Runtime:
    """Load config and build everything.

    Defaults come from the environment: AIKIT_CONFIG (config path) and
    AIKIT_OFFLINE (swap LLMs and embedders for fakes).
    """
    if env_file and Path(env_file).is_file():
        load_dotenv(env_file, override=False)
    path = config_path or os.environ.get("AIKIT_CONFIG", DEFAULT_CONFIG)
    if offline is None:
        offline = _truthy(os.environ.get("AIKIT_OFFLINE"))

    config = load_config(path, overrides=overrides, offline=offline)
    obs = config.observability
    configure_logging(log_level or obs.log_level, obs.log_format)

    _import_project_modules(config.imports)
    load_plugins(config.plugins)

    builder = Builder(config.components)
    flow = builder.build(config.flow, "flow", path="flow")
    if not isinstance(flow, QueryFlow):
        raise ConfigError("flow: the configured flow must provide run() and stream()")

    ingest_spec = _ingest_spec(config)
    ingest = builder.build(ingest_spec, "flow", path="ingest") if ingest_spec else None
    if ingest is not None and not isinstance(ingest, IngestFlow):
        raise ConfigError("ingest: must build an ingest flow")

    tracer = Tracer(
        enabled=obs.tracing,
        service_name=obs.service_name or config.app.name,
        endpoint=obs.otlp_endpoint,
    )
    add_hook = getattr(flow, "add_hook", None)
    if add_hook is not None:
        add_hook(TelemetryHook(tracer, obs.costs), first=True)

    return Runtime(config=config, builder=builder, flow=flow, ingest=ingest, tracer=tracer)
