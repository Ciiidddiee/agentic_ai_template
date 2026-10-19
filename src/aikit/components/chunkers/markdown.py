from __future__ import annotations

import re

from aikit.components.chunkers._split import make_chunk, split_text, validate_sizes
from aikit.core.registry import register
from aikit.core.types import Chunk, Document

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


def sections(text: str) -> list[tuple[list[str], str]]:
    """Split Markdown into (heading path, body) sections, ignoring headings inside code fences."""
    result: list[tuple[list[str], str]] = []
    path: list[str] = []
    lines: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
        match = None if in_fence else _HEADING.match(line)
        if match:
            if "\n".join(lines).strip():
                result.append((list(path), "\n".join(lines)))
            level = len(match.group(1))
            path = [*path[: level - 1], match.group(2)]
            lines = [line]
        else:
            lines.append(line)
    if "\n".join(lines).strip():
        result.append((list(path), "\n".join(lines)))
    return result


@register("chunker", "markdown")
class MarkdownChunker:
    """Chunks along Markdown headings; oversized sections are split recursively.

    Each chunk gets `section` metadata like "Refunds > Opened items".
    """

    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 100) -> None:
        validate_sizes(chunk_size, chunk_overlap)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split(self, document: Document) -> list[Chunk]:
        chunks: list[Chunk] = []
        for heading_path, body in sections(document.text):
            section = " > ".join(heading_path)
            for piece in split_text(body, self.chunk_size, self.chunk_overlap):
                extra = {"section": section} if section else {}
                chunks.append(make_chunk(document, piece, len(chunks), extra))
        return chunks
