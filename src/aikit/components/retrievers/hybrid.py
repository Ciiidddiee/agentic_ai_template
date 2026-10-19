from __future__ import annotations

from typing import Any

from aikit.components._text import cosine
from aikit.core.errors import ConfigError
from aikit.core.ports import Embedder, KeywordSearchable, VectorStore
from aikit.core.registry import register
from aikit.core.types import ScoredChunk


@register("retriever", "hybrid")
class HybridRetriever:
    """Dense + keyword (BM25) search fused with weighted reciprocal rank fusion.

    `alpha` weights the dense ranking (1.0 = dense only, 0.0 = keyword only).
    Results are ordered by the fused rank, but `score` is the cosine similarity
    to the query so thresholds like `min_score` mean the same as for dense.
    """

    def __init__(
        self,
        store: VectorStore,
        embedder: Embedder,
        top_k: int = 5,
        alpha: float = 0.5,
        candidates: int = 20,
        rrf_k: int = 60,
        filters: dict[str, Any] | None = None,
    ) -> None:
        if not isinstance(store, KeywordSearchable):
            raise ConfigError(
                "hybrid retriever needs a store with keyword_search; "
                f"{type(store).__name__} has none"
            )
        if not 0.0 <= alpha <= 1.0:
            raise ConfigError("alpha must be between 0 and 1")
        self.store = store
        self.keyword_store: KeywordSearchable = store
        self.embedder = embedder
        self.top_k = top_k
        self.alpha = alpha
        self.candidates = candidates
        self.rrf_k = rrf_k
        self.filters = filters or {}

    async def retrieve(
        self,
        query: str,
        *,
        top_k: int | None = None,
        filters: dict[str, Any] | None = None,
        groups: list[str] | None = None,
    ) -> list[ScoredChunk]:
        merged_filters = {**self.filters, **(filters or {})}
        vector = await self.embedder.embed_query(query)
        dense = await self.store.search(
            vector, top_k=self.candidates, filters=merged_filters, groups=groups
        )
        keyword = await self.keyword_store.keyword_search(
            query, top_k=self.candidates, filters=merged_filters, groups=groups
        )

        fused: dict[str, float] = {}
        by_id: dict[str, ScoredChunk] = {}
        for weight, results in ((self.alpha, dense), (1 - self.alpha, keyword)):
            for rank, item in enumerate(results):
                fused[item.chunk.id] = fused.get(item.chunk.id, 0.0) + weight / (
                    self.rrf_k + rank + 1
                )
                by_id.setdefault(item.chunk.id, item)

        ranked = sorted(fused, key=lambda chunk_id: fused[chunk_id], reverse=True)
        output = []
        for chunk_id in ranked[: top_k or self.top_k]:
            chunk = by_id[chunk_id].chunk
            score = cosine(vector, chunk.embedding) if chunk.embedding else by_id[chunk_id].score
            output.append(ScoredChunk(chunk=chunk, score=score))
        return output
