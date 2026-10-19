from __future__ import annotations

import importlib

from pydantic import BaseModel, ValidationError

from aikit.core.context import RunContext
from aikit.core.errors import ConfigError, GuardrailViolationError
from aikit.core.registry import register


def import_model(dotted: str) -> type[BaseModel]:
    module_name, _, attr = dotted.partition(":")
    if not attr:
        raise ConfigError(f"model must look like 'package.module:ClassName', got '{dotted}'")
    try:
        model = getattr(importlib.import_module(module_name), attr)
    except (ImportError, AttributeError) as exc:
        raise ConfigError(f"Cannot import output schema '{dotted}': {exc}") from exc
    if not (isinstance(model, type) and issubclass(model, BaseModel)):
        raise ConfigError(f"'{dotted}' is not a pydantic model")
    return model


@register("guardrail", "output_schema")
class OutputSchemaGuardrail:
    """Requires the final answer to be JSON matching a pydantic model, e.g.
    `model: project.domain.schemas:TriageResult`. Code fences around the JSON are tolerated."""

    name = "output_schema"

    def __init__(self, model: str, stages: list[str] | None = None) -> None:
        self.model = import_model(model)
        self.stages = frozenset(stages or ["output"])

    async def apply(self, text: str, *, stage: str, ctx: RunContext) -> str:
        payload = text.strip()
        if payload.startswith("```"):
            payload = payload.strip("`")
            payload = payload.split("\n", 1)[1] if "\n" in payload else payload
        try:
            parsed = self.model.model_validate_json(payload)
        except ValidationError as exc:
            raise GuardrailViolationError(
                f"Output does not match {self.model.__name__}: {exc.error_count()} error(s)",
                guardrail=self.name,
                stage=stage,
            ) from exc
        return parsed.model_dump_json()
