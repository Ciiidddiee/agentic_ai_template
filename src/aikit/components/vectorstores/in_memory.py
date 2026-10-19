from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from aikit.components._text import BM25, cosine
from aikit.core.errors import ConfigError
from aikit.core.filters import acl_allows, matches_filters
from aikit.core.registry import register
from aikit.core.types import Chunk, ScoredChunk


@register("vector_store", "in_memory")
class InMemoryVectorStore:
    """Brute-force vector + BM25 store. Good for development, tests, and a few
    tens of thousands of chunks. With `path`, the index is saved as JSON after
    every write and reloaded on startup."""

    def __init__(self, path: str | None = None) -> None:
        self.path = Path(path) if path else None
        self._chunks: dict[str, Chunk] = {}
        self._bm25: BM25 | None = None
        self._bm25_ids: list[str] = []
        if self.path and self.path.is_file():
            self._load()

    def _load(self) -> None:
        assert self.path is not None
        try:
            items = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ConfigError(f"Corrupt vector index at {self.path}: {exc}") from exc
        self._chunks = {item["id"]: Chunk.model_validate(item) for item in items}

    def _persist(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(
            json.dumps([c.model_dump(mode="json") for c in self._chunks.values()]),
            encoding="utf-8",
        )
        os.replace(tmp, self.path)

    def _candidates(self, filters: dict[str, Any] | None, groups: list[str] | None) -> list[Chunk]:
        return [
            c
            for c in self._chunks.values()
            if matches_filters(c.metadata, filters) and acl_allows(c.metadata, groups)
        ]

    async def upsert(self, chunks: list[Chunk]) -> None:
        for chunk in chunks:
            if chunk.embedding is None:
                raise ValueError(f"Chunk {chunk.id} has no embedding")
            self._chunks[chunk.id] = chunk
        self._bm25 = None
        self._persist()

    async def search(
        self,
        vector: list[float],
        *,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
        groups: list[str] | None = None,
    ) -> list[ScoredChunk]:
        scored = [
            ScoredChunk(chunk=c, score=cosine(vector, c.embedding or []))
            for c in self._candidates(filters, groups)
        ]
        scored.sort(key=lambda s: s.score, reverse=True)
        return scored[:top_k]

    async def keyword_search(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
        groups: list[str] | None = None,
    ) -> list[ScoredChunk]:
        if self._bm25 is None:
            self._bm25_ids = list(self._chunks)
            self._bm25 = BM25([self._chunks[i].text for i in self._bm25_ids])
        allowed = {c.id for c in self._candidates(filters, groups)}
        scored = [
            ScoredChunk(chunk=self._chunks[chunk_id], score=score)
            for chunk_id, score in zip(self._bm25_ids, self._bm25.scores(query), strict=True)
            if chunk_id in allowed and score > 0
        ]
        scored.sort(key=lambda s: s.score, reverse=True)
        return scored[:top_k]

    async def delete(self, ids: list[str]) -> None:
        for chunk_id in ids:
            self._chunks.pop(chunk_id, None)
        self._bm25 = None
        self._persist()

    async def ids(self, filters: dict[str, Any] | None = None) -> set[str]:
        return {c.id for c in self._chunks.values() if matches_filters(c.metadata, filters)}

    async def count(self) -> int:
        return len(self._chunks)
