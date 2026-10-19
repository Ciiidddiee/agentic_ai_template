from __future__ import annotations

import pytest

from aikit.components.chunkers.markdown import MarkdownChunker
from aikit.components.chunkers.recursive import RecursiveChunker
from aikit.core.ports import Chunker
from aikit.core.types import Document

DOC = Document(
    id="doc-1",
    text="# Title\n\n" + "\n\n".join(f"Paragraph {i}. " + "words " * 40 for i in range(10)),
    metadata={"source": "guide.md", "acl": ["team"]},
)


@pytest.mark.parametrize(
    "chunker",
    [
        RecursiveChunker(chunk_size=300, chunk_overlap=50),
        MarkdownChunker(chunk_size=300, chunk_overlap=50),
    ],
    ids=["recursive", "markdown"],
)
class TestChunkerContract:
    def test_satisfies_protocol(self, chunker: Chunker) -> None:
        assert isinstance(chunker, Chunker)

    def test_chunks_are_bounded_and_non_empty(self, chunker: Chunker) -> None:
        chunks = chunker.split(DOC)
        assert len(chunks) > 1
        assert all(c.text.strip() and len(c.text) <= 300 for c in chunks)

    def test_metadata_is_inherited(self, chunker: Chunker) -> None:
        for chunk in chunker.split(DOC):
            assert chunk.document_id == "doc-1"
            assert chunk.metadata["source"] == "guide.md"
            assert chunk.metadata["acl"] == ["team"]
            assert chunk.metadata["document_id"] == "doc-1"

    def test_ids_are_unique_and_stable(self, chunker: Chunker) -> None:
        first = [c.id for c in chunker.split(DOC)]
        assert len(set(first)) == len(first)
        assert first == [c.id for c in chunker.split(DOC)]
