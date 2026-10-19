from __future__ import annotations

import hashlib
from typing import Any

from aikit.core.errors import ConfigError
from aikit.core.types import Chunk, Document

DEFAULT_SEPARATORS = ("\n\n", "\n", ". ", " ", "")


def validate_sizes(chunk_size: int, chunk_overlap: int) -> None:
    if chunk_size <= 0:
        raise ConfigError("chunk_size must be positive")
    if not 0 <= chunk_overlap < chunk_size:
        raise ConfigError("chunk_overlap must be >= 0 and smaller than chunk_size")


def split_text(
    text: str, size: int, overlap: int, separators: tuple[str, ...] = DEFAULT_SEPARATORS
) -> list[str]:
    """Recursive character splitting: prefer paragraph, then line, sentence, word boundaries."""
    if len(text) <= size:
        return [text.strip()] if text.strip() else []

    separator = separators[-1] if separators else ""
    remaining: tuple[str, ...] = ()
    for i, candidate in enumerate(separators):
        if candidate == "" or candidate in text:
            separator, remaining = candidate, separators[i + 1 :]
            break

    pieces = text.split(separator) if separator else list(text)
    atoms: list[str] = []
    for piece in pieces:
        if len(piece) > size and remaining:
            atoms.extend(split_text(piece, size, overlap, remaining))
        elif piece:
            atoms.append(piece)

    chunks: list[str] = []
    current: list[str] = []
    length = 0
    for atom in atoms:
        added = len(atom) + (len(separator) if current else 0)
        if current and length + added > size:
            chunks.append(separator.join(current))
            while current and (length > overlap or length + len(atom) + len(separator) > size):
                length -= len(current[0]) + (len(separator) if len(current) > 1 else 0)
                current.pop(0)
        current.append(atom)
        length += len(atom) + (len(separator) if len(current) > 1 else 0)
    if current:
        chunks.append(separator.join(current))
    return [c.strip() for c in chunks if c.strip()]


def make_chunk(document: Document, text: str, index: int, extra: dict[str, Any]) -> Chunk:
    """Chunk ids hash the source and text, so re-ingesting unchanged content is a no-op."""
    source = str(document.metadata.get("source", document.id))
    digest = hashlib.sha256(f"{source}\n{text}".encode()).hexdigest()[:32]
    metadata = {**document.metadata, **extra, "document_id": document.id, "chunk_index": index}
    return Chunk(id=digest, document_id=document.id, text=text, metadata=metadata)
