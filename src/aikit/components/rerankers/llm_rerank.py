from __future__ import annotations

import json
import re

from aikit.core.ports import LLM
from aikit.core.registry import register
from aikit.core.types import Message, ScoredChunk

SYSTEM_PROMPT = (
    "You rank passages by how well they answer a question. "
    "Respond with JSON only: an array of passage numbers, most relevant first, "
    "omitting irrelevant passages. Example: [3, 1]"
)
_ARRAY = re.compile(r"\[[\d,\s]*\]")


@register("reranker", "llm_rerank")
class LLMReranker:
    """Asks the LLM to order passages. Falls back to retrieval order if the reply is unusable."""

    def __init__(self, llm: LLM, top_n: int = 5, max_chars: int = 600) -> None:
        self.llm = llm
        self.top_n = top_n
        self.max_chars = max_chars

    async def rerank(self, query: str, chunks: list[ScoredChunk]) -> list[ScoredChunk]:
        if len(chunks) <= 1:
            return chunks[: self.top_n]
        passages = "\n\n".join(
            f"[{i}] {item.chunk.text[: self.max_chars]}" for i, item in enumerate(chunks, start=1)
        )
        response = await self.llm.chat(
            [
                Message.system(SYSTEM_PROMPT),
                Message.user(f"Question: {query}\n\nPassages:\n{passages}"),
            ],
            temperature=0,
        )
        order = self._parse(response.content or "", len(chunks))
        if not order:
            return chunks[: self.top_n]
        seen = set(order)
        ranked = [chunks[i - 1] for i in order] + [
            c for i, c in enumerate(chunks, start=1) if i not in seen
        ]
        return ranked[: self.top_n]

    @staticmethod
    def _parse(text: str, count: int) -> list[int]:
        match = _ARRAY.search(text)
        if not match:
            return []
        try:
            values = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []
        order: list[int] = []
        for value in values:
            if isinstance(value, int) and 1 <= value <= count and value not in order:
                order.append(value)
        return order
