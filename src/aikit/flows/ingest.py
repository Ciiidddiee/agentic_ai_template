from __future__ import annotations

import time
from datetime import UTC, datetime

from aikit.core.ports import Chunker, Embedder, Loader, VectorStore
from aikit.core.registry import register
from aikit.core.types import Chunk, IngestReport


@register("flow", "ingest")
class IngestFlow:
    """Load -> chunk -> embed -> upsert, idempotently.

    Chunk ids are content hashes, so unchanged chunks are skipped (no embedding
    cost) and chunks that disappeared from an edited document are deleted.
    With `prune`, chunks of documents no longer returned by any loader are
    deleted too; only enable it when this flow owns the whole store.
    """

    def __init__(
        self,
        loaders: list[Loader],
        chunker: Chunker,
        embedder: Embedder,
        store: VectorStore,
        batch_size: int = 64,
        prune: bool = False,
    ) -> None:
        self.loaders = loaders
        self.chunker = chunker
        self.embedder = embedder
        self.store = store
        self.batch_size = batch_size
        self.prune = prune

    async def run(self) -> IngestReport:
        started = time.perf_counter()
        report = IngestReport()
        documents = [doc for loader in self.loaders for doc in await loader.load()]
        report.documents = len(documents)
        now = datetime.now(UTC).isoformat()

        pending: list[Chunk] = []
        current_ids: set[str] = set()
        for document in documents:
            chunks = self.chunker.split(document)
            report.chunks += len(chunks)
            new_ids = {c.id for c in chunks}
            current_ids |= new_ids
            existing = await self.store.ids({"document_id": document.id})
            stale = existing - new_ids
            if stale:
                await self.store.delete(sorted(stale))
                report.deleted += len(stale)
            fresh = [c for c in chunks if c.id not in existing]
            report.unchanged += len(chunks) - len(fresh)
            for chunk in fresh:
                chunk.metadata.update(ingested_at=now, embedding_model=self.embedder.model)
            pending.extend(fresh)

        for start in range(0, len(pending), self.batch_size):
            batch = pending[start : start + self.batch_size]
            vectors = await self.embedder.embed([c.text for c in batch])
            for chunk, vector in zip(batch, vectors, strict=True):
                chunk.embedding = vector
            await self.store.upsert(batch)
            report.embedded += len(batch)

        if self.prune:
            orphaned = await self.store.ids() - current_ids
            if orphaned:
                await self.store.delete(sorted(orphaned))
                report.deleted += len(orphaned)

        report.duration_s = round(time.perf_counter() - started, 3)
        return report
