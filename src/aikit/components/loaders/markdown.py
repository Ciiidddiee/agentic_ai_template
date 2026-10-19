from __future__ import annotations

from typing import Any

import yaml

from aikit.components.loaders._base import DEFAULT_EXCLUDE, find_files, make_document
from aikit.core.registry import register
from aikit.core.types import Document


def split_front_matter(text: str) -> tuple[dict[str, Any], str]:
    """Return YAML front matter (between leading `---` lines) and the remaining body."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("\n---", 1)
    if len(parts) != 2:
        return {}, text
    header = parts[0].lstrip("-").strip()
    body = parts[1].split("\n", 1)[1] if "\n" in parts[1] else ""
    try:
        meta = yaml.safe_load(header) or {}
    except yaml.YAMLError:
        return {}, text
    return (meta if isinstance(meta, dict) else {}), body


@register("loader", "markdown")
class MarkdownLoader:
    """Markdown files. YAML front matter (title, acl, tags, ...) becomes document metadata."""

    def __init__(
        self,
        path: str,
        glob: str = "**/*.md",
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
        documents = []
        for path in find_files(self.path, self.glob, self.exclude):
            front, body = split_front_matter(path.read_text(encoding=self.encoding))
            documents.append(make_document(path, body, {**self.metadata, **front}))
        return documents
