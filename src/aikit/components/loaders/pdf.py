from __future__ import annotations

from typing import Any

from aikit.components.loaders._base import find_files, make_document
from aikit.core.errors import ConfigError
from aikit.core.registry import register
from aikit.core.types import Document


@register("loader", "pdf")
class PdfLoader:
    """PDF files, one document per page (requires the `loaders` extra: pypdf)."""

    def __init__(
        self, path: str, glob: str = "**/*.pdf", metadata: dict[str, Any] | None = None
    ) -> None:
        self.path = path
        self.glob = glob
        self.metadata = metadata or {}

    async def load(self) -> list[Document]:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ConfigError("The pdf loader needs pypdf: install aikit[loaders]") from exc

        documents = []
        for path in find_files(self.path, self.glob):
            reader = PdfReader(str(path))
            for number, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ""
                if text.strip():
                    documents.append(make_document(path, text, dict(self.metadata), page=number))
        return documents
