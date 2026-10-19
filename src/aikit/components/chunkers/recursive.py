from __future__ import annotations

from aikit.components.chunkers._split import (
    DEFAULT_SEPARATORS,
    make_chunk,
    split_text,
    validate_sizes,
)
from aikit.core.registry import register
from aikit.core.types import Chunk, Document


@register("chunker", "recursive")
class RecursiveChunker:
    """Splits on paragraph, line, sentence, then word boundaries. Sizes are in characters."""

    def __init__(
        self,
        chunk_size: int = 800,
        chunk_overlap: int = 100,
        separators: list[str] | None = None,
    ) -> None:
        validate_sizes(chunk_size, chunk_overlap)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = tuple(separators) if separators else DEFAULT_SEPARATORS

    def split(self, document: Document) -> list[Chunk]:
        pieces = split_text(document.text, self.chunk_size, self.chunk_overlap, self.separators)
        return [make_chunk(document, text, i, {}) for i, text in enumerate(pieces)]
