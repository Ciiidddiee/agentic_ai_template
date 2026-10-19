from __future__ import annotations

from aikit.core.registry import register
from aikit.core.types import ScoredChunk


@register("reranker", "passthrough")
class PassthroughReranker:
    """Keeps retrieval order and truncates to `top_n`.

    A placeholder until you add a real reranker (cross-encoder service, `llm_rerank`).
    """

    def __init__(self, top_n: int = 5) -> None:
        self.top_n = top_n

    async def rerank(self, query: str, chunks: list[ScoredChunk]) -> list[ScoredChunk]:
        return chunks[: self.top_n]
