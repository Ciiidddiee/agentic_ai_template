from __future__ import annotations

from typing import Any

from aikit.components.loaders._base import DEFAULT_EXCLUDE, find_files, make_document
from aikit.core.registry import register
from aikit.core.types import Document


@register("loader", "text")
class TextLoader:
    """Plain-text files. `metadata` (for example `acl: [hr]`) is added to every document."""

    def __init__(
        self,
        path: str,
        glob: str = "**/*.txt",
        metadata: dict[str, Any] | None = None,
        encoding: str = "utf-8",
        exclude: list[str] | None = None,
    ) -> None:
        self.path = path
        self.glob = glob
        self.metadata = metadata or {}
        self.encoding = encoding
        self.exclude = list(DEFAULT_EXCLUDE) if exclude is None else exclude

    async def load(self) -> list[Document]:
        return [
            make_document(p, p.read_text(encoding=self.encoding), dict(self.metadata))
            for p in find_files(self.path, self.glob, self.exclude)
        ]
