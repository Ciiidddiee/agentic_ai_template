from __future__ import annotations

from aikit.core.registry import register
from aikit.core.types import Message


def trim_history(messages: list[Message], max_messages: int) -> list[Message]:
    """Keep the last `max_messages`, starting at a user turn so tool results are never orphaned."""
    trimmed = messages[-max_messages:] if max_messages > 0 else []
    while trimmed and trimmed[0].role != "user":
        trimmed = trimmed[1:]
    return trimmed


@register("memory", "buffer")
class BufferMemory:
    """Per-session conversation window held in process memory."""

    def __init__(self, max_messages: int = 20) -> None:
        self.max_messages = max_messages
        self._sessions: dict[str, list[Message]] = {}

    async def load(self, session_id: str) -> list[Message]:
        return list(self._sessions.get(session_id, []))

    async def save(self, session_id: str, messages: list[Message]) -> None:
        history = [m for m in messages if m.role != "system"]
        self._sessions[session_id] = trim_history(history, self.max_messages)
