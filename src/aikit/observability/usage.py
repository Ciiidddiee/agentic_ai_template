from __future__ import annotations

from collections.abc import Mapping

from aikit.core.config import ModelCost
from aikit.core.types import Usage


def estimate_cost(usage: Usage, model: str | None, costs: Mapping[str, ModelCost]) -> float | None:
    """Cost in your configured currency, or None if the model has no price entry.

    Internal gateways often charge back per team; put those rates under
    `observability.costs` keyed by model name (or `default`).
    """
    price = costs.get(model or "") or costs.get("default")
    if price is None:
        return None
    return (
        usage.prompt_tokens / 1000 * price.input_per_1k
        + usage.completion_tokens / 1000 * price.output_per_1k
    )
