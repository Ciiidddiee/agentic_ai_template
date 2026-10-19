from __future__ import annotations

import copy
from typing import Any


class InMemoryRunStore:
    """Default store for paused runs. Lost on restart; use a persistent RunStore in production."""

    def __init__(self) -> None:
        self._runs: dict[str, dict[str, Any]] = {}

    async def save(self, run_id: str, state: dict[str, Any]) -> None:
        self._runs[run_id] = copy.deepcopy(state)

    async def load(self, run_id: str) -> dict[str, Any] | None:
        state = self._runs.get(run_id)
        return copy.deepcopy(state) if state is not None else None

    async def delete(self, run_id: str) -> None:
        self._runs.pop(run_id, None)
