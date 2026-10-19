from __future__ import annotations

import pytest

from aikit.components.chunkers._split import split_text
from aikit.components.chunkers.markdown import MarkdownChunker, sections
from aikit.components.chunkers.recursive import RecursiveChunker
from aikit.core.errors import ConfigError
from aikit.core.types import Document

TEXT = " ".join(f"Sentence number {i} talks about refunds." for i in range(60))


def test_split_respects_size() -> None:
    pieces = split_text(TEXT, size=200, overlap=40)
    assert len(pieces) > 5
    assert all(len(p) <= 200 for p in pieces)


def test_split_overlaps_neighbouring_chunks() -> None:
    pieces = split_text(TEXT, size=200, overlap=80)
    shared = set(pieces[0].split()) & set(pieces[1].split())
    assert shared


def test_short_text_is_one_chunk() -> None:
    assert split_text("hello", size=100, overlap=10) == ["hello"]
    assert split_text("   ", size=100, overlap=10) == []


def test_invalid_sizes() -> None:
    with pytest.raises(ConfigError):
        RecursiveChunker(chunk_size=100, chunk_overlap=100)


def test_markdown_sections_track_heading_path() -> None:
    text = "# Refunds\nintro\n## Opened items\nfee\n```\n# not a heading\n```\n# Shipping\nfast"
    result = sections(text)
    assert [path for path, _ in result] == [["Refunds"], ["Refunds", "Opened items"], ["Shipping"]]
    assert "# not a heading" in result[1][1]


def test_markdown_chunker_sets_section_metadata() -> None:
    doc = Document(id="d1", text="# A\none\n## B\ntwo", metadata={"source": "x.md"})
    chunks = MarkdownChunker(chunk_size=100, chunk_overlap=0).split(doc)
    assert [c.metadata["section"] for c in chunks] == ["A", "A > B"]
    assert all(c.metadata["document_id"] == "d1" for c in chunks)


def test_chunk_ids_are_deterministic_content_hashes() -> None:
    doc = Document(id="d1", text=TEXT, metadata={"source": "x.md"})
    first = RecursiveChunker(chunk_size=200, chunk_overlap=20).split(doc)
    second = RecursiveChunker(chunk_size=200, chunk_overlap=20).split(doc)
    assert [c.id for c in first] == [c.id for c in second]
    assert len({c.id for c in first}) == len(first)
