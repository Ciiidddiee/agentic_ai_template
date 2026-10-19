from __future__ import annotations

import pytest

from aikit.components._text import cosine
from aikit.components.embeddings.fake import FakeEmbedder
from aikit.components.embeddings.openai_compat import OpenAICompatEmbedder
from aikit.core.ports import Embedder
from tests.contract.gateway import MockGateway


class EmbedderContract:
    @pytest.fixture
    def embedder(self) -> Embedder:
        raise NotImplementedError

    def test_satisfies_protocol(self, embedder: Embedder) -> None:
        assert isinstance(embedder, Embedder)

    async def test_one_vector_per_text_with_consistent_dimensions(self, embedder: Embedder) -> None:
        texts = ["refund policy", "shipping times", "warranty claims", "returns", "express"]
        vectors = await embedder.embed(texts)
        assert len(vectors) == len(texts)
        assert len({len(v) for v in vectors}) == 1
        query = await embedder.embed_query("refund")
        assert len(query) == len(vectors[0])

    async def test_order_is_preserved(self, embedder: Embedder) -> None:
        vectors = await embedder.embed(["alpha beta", "gamma delta"])
        again = await embedder.embed(["gamma delta"])
        assert cosine(vectors[1], again[0]) == pytest.approx(1.0)

    async def test_similar_texts_score_higher(self, embedder: Embedder) -> None:
        query = await embedder.embed_query("refund window for returns")
        related, unrelated = await embedder.embed(
            ["returns within the refund window", "express shipping costs fifteen dollars"]
        )
        assert cosine(query, related) > cosine(query, unrelated)


class TestFakeEmbedder(EmbedderContract):
    @pytest.fixture
    def embedder(self) -> Embedder:
        return FakeEmbedder()


class TestOpenAICompatEmbedder(EmbedderContract):
    @pytest.fixture
    def embedder(self) -> Embedder:
        embedder = OpenAICompatEmbedder(model="e", base_url="https://gateway.test/v1", batch_size=2)
        embedder.http._transport = MockGateway().transport
        return embedder


async def test_openai_compat_embedder_batches_and_prefixes() -> None:
    gateway = MockGateway()
    embedder = OpenAICompatEmbedder(
        model="e", base_url="https://gateway.test/v1", batch_size=2, document_prefix="passage: "
    )
    embedder.http._transport = gateway.transport
    await embedder.embed(["a", "b", "c", "d", "e"])
    assert [len(r["input"]) for r in gateway.requests] == [2, 2, 1]
    assert gateway.requests[0]["input"][0] == "passage: a"
