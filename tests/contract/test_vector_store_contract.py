from __future__ import annotations

from pathlib import Path

import pytest

from aikit.components.embeddings.fake import FakeEmbedder
from aikit.components.vectorstores.in_memory import InMemoryVectorStore
from aikit.core.ports import KeywordSearchable, VectorStore
from aikit.core.types import Chunk

EMBEDDER = FakeEmbedder()


async def make_chunks() -> list[Chunk]:
    rows = [
        ("c1", "d1", "Refunds are accepted within 30 days.", {"tag": "refunds"}),
        ("c2", "d1", "Opened items have a restocking fee.", {"tag": "refunds"}),
        ("c3", "d2", "Express shipping takes two days.", {"tag": "shipping"}),
        ("c4", "d3", "Leads may grant goodwill credit.", {"tag": "internal", "acl": ["leads"]}),
    ]
    vectors = await EMBEDDER.embed([r[2] for r in rows])
    return [
        Chunk(
            id=cid,
            document_id=doc,
            text=text,
            metadata={**meta, "document_id": doc, "source": f"{doc}.md"},
            embedding=vec,
        )
        for (cid, doc, text, meta), vec in zip(rows, vectors, strict=True)
    ]


class VectorStoreContract:
    @pytest.fixture
    def store(self, tmp_path: Path) -> VectorStore:
        raise NotImplementedError

    @pytest.fixture
    async def filled(self, store: VectorStore) -> VectorStore:
        await store.upsert(await make_chunks())
        return store

    def test_satisfies_protocol(self, store: VectorStore) -> None:
        assert isinstance(store, VectorStore)

    async def test_search_orders_by_similarity(self, filled: VectorStore) -> None:
        query = await EMBEDDER.embed_query("refunds within 30 days")
        results = await filled.search(query, top_k=2)
        assert results[0].chunk.id == "c1"
        assert results[0].score >= results[1].score

    async def test_metadata_filters(self, filled: VectorStore) -> None:
        query = await EMBEDDER.embed_query("refunds")
        results = await filled.search(query, top_k=10, filters={"tag": "shipping"})
        assert [r.chunk.id for r in results] == ["c3"]

    async def test_acl_hides_restricted_chunks(self, filled: VectorStore) -> None:
        query = await EMBEDDER.embed_query("goodwill credit")
        public = await filled.search(query, top_k=10, groups=[])
        lead = await filled.search(query, top_k=10, groups=["leads"])
        assert "c4" not in {r.chunk.id for r in public}
        assert "c4" in {r.chunk.id for r in lead}

    async def test_ids_delete_count(self, filled: VectorStore) -> None:
        assert await filled.count() == 4
        assert await filled.ids({"document_id": "d1"}) == {"c1", "c2"}
        await filled.delete(["c1"])
        assert await filled.count() == 3
        assert await filled.ids({"document_id": "d1"}) == {"c2"}

    async def test_upsert_replaces_by_id(self, filled: VectorStore) -> None:
        chunk = (await make_chunks())[0]
        chunk.text = "updated"
        await filled.upsert([chunk])
        assert await filled.count() == 4

    async def test_upsert_requires_embeddings(self, store: VectorStore) -> None:
        with pytest.raises(ValueError):
            await store.upsert([Chunk(id="x", document_id="d", text="t")])


class TestInMemoryVectorStore(VectorStoreContract):
    @pytest.fixture
    def store(self, tmp_path: Path) -> VectorStore:
        return InMemoryVectorStore(path=str(tmp_path / "index.json"))

    async def test_keyword_search(self, filled: VectorStore) -> None:
        assert isinstance(filled, KeywordSearchable)
        results = await filled.keyword_search("restocking fee", top_k=3, groups=[])
        assert results[0].chunk.id == "c2"

    async def test_persists_across_instances(self, filled: VectorStore, tmp_path: Path) -> None:
        reopened = InMemoryVectorStore(path=str(tmp_path / "index.json"))
        assert await reopened.count() == 4
