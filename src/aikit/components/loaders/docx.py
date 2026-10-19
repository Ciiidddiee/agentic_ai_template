from __future__ import annotations

from typing import Any

from aikit.components.loaders._base import find_files, make_document
from aikit.core.errors import ConfigError
from aikit.core.registry import register
from aikit.core.types import Document


@register("loader", "docx")
class DocxLoader:
    """Word documents; headings become Markdown headings (requires the `loaders` extra)."""

    def __init__(
        self, path: str, glob: str = "**/*.docx", metadata: dict[str, Any] | None = None
    ) -> None:
        self.path = path
        self.glob = glob
        self.metadata = metadata or {}

    async def load(self) -> list[Document]:
        try:
            import docx
        except ImportError as exc:
            raise ConfigError("The docx loader needs python-docx: install aikit[loaders]") from exc

        documents = []
        for path in find_files(self.path, self.glob):
            lines = []
            for paragraph in docx.Document(str(path)).paragraphs:
                text = paragraph.text.strip()
                if not text:
                    continue
                style = (paragraph.style.name if paragraph.style is not None else "") or ""
                if style.startswith("Heading") and style[-1:].isdigit():
                    text = "#" * int(style[-1]) + " " + text
                lines.append(text)
            documents.append(make_document(path, "\n\n".join(lines), dict(self.metadata)))
        return documents
