from __future__ import annotations

from aikit.components.memory.buffer import trim_history
from aikit.core.ports import LLM
from aikit.core.registry import register
from aikit.core.types import Message

SUMMARY_PREFIX = "Summary of the earlier conversation: "
SUMMARY_PROMPT = (
    "Summarise the conversation below in a few sentences. Keep names, numbers, "
    "decisions, and open questions. Write in the third person."
)


@register("memory", "summary")
class SummaryMemory:
    """Keeps the last `keep_last` messages verbatim and folds older ones into an LLM summary."""

    def __init__(self, llm: LLM, max_messages: int = 20, keep_last: int = 8) -> None:
        if keep_last >= max_messages:
            raise ValueError("keep_last must be smaller than max_messages")
        self.llm = llm
        self.max_messages = max_messages
        self.keep_last = keep_last
        self._sessions: dict[str, list[Message]] = {}

    async def load(self, session_id: str) -> list[Message]:
        return list(self._sessions.get(session_id, []))

    async def save(self, session_id: str, messages: list[Message]) -> None:
        history = [m for m in messages if m.role != "system" or SUMMARY_PREFIX in (m.content or "")]
        if len(history) <= self.max_messages:
            self._sessions[session_id] = history
            return
        recent = trim_history(history, self.keep_last)
        older = history[: len(history) - len(recent)]
        transcript = "\n".join(
            f"{m.role}: {m.content}" for m in older if m.content and m.role != "tool"
        )
        response = await self.llm.chat(
            [Message.system(SUMMARY_PROMPT), Message.user(transcript)], temperature=0
        )
        summary = Message.system(SUMMARY_PREFIX + (response.content or "").strip())
        self._sessions[session_id] = [summary, *recent]
