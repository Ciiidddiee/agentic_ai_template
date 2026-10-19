from __future__ import annotations

from typing import Any

from aikit.core.ports import Embedder, VectorStore
from aikit.core.registry import register
from aikit.core.types import ScoredChunk


@register("retriever", "dense")
class DenseRetriever:
    """Embedding similarity search. `filters` are applied to every query."""

    def __init__(
        self,
        store: VectorStore,
        embedder: Embedder,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> None:
        self.store = store
        self.embedder = embedder
        self.top_k = top_k
        self.filters = filters or {}

    async def retrieve(
        self,
        query: str,
        *,
        top_k: int | None = None,
        filters: dict[str, Any] | None = None,
        groups: list[str] | None = None,
    ) -> list[ScoredChunk]:
        vector = await self.embedder.embed_query(query)
        return await self.store.search(
            vector,
            top_k=top_k or self.top_k,
            filters={**self.filters, **(filters or {})},
            groups=groups,
        )
