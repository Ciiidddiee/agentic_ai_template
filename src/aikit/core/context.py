from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from aikit.core.types import Usage, new_id


@dataclass
class RunContext:
    """Per-request state passed through flows, tools, and hooks.

    `groups` drives document ACL filtering: chunks with an `acl` list are only
    visible when it shares at least one group with the caller. An empty list
    means the caller only sees public chunks.
    """

    run_id: str = field(default_factory=lambda: new_id("run_"))
    session_id: str | None = None
    user_id: str | None = None
    groups: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    usage: Usage = field(default_factory=Usage)
    timeout_s: float | None = None
    started_at: float = field(default_factory=time.monotonic)

    def elapsed(self) -> float:
        return time.monotonic() - self.started_at

    def remaining(self) -> float | None:
        if self.timeout_s is None:
            return None
        return max(0.0, self.timeout_s - self.elapsed())

    def timed_out(self) -> bool:
        remaining = self.remaining()
        return remaining is not None and remaining <= 0
