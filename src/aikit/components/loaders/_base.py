from __future__ import annotations

import hashlib
from collections.abc import Sequence
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from aikit.core.errors import ConfigError
from aikit.core.types import Document

# Folder docs and AI context files live next to data; never index them by accident.
DEFAULT_EXCLUDE = ("README.md", "AGENTS.md", "CLAUDE.md", "GEMINI.md")


def find_files(path: str, pattern: str, exclude: Sequence[str] = ()) -> list[Path]:
    root = Path(path)
    if root.is_file():
        return [root]
    if not root.exists():
        raise ConfigError(f"Loader path does not exist: {root}")
    return sorted(
        p
        for p in root.glob(pattern)
        if p.is_file() and not any(fnmatch(p.name, rule) for rule in exclude)
    )


def source_name(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def make_document(
    path: Path, text: str, metadata: dict[str, Any], page: int | None = None
) -> Document:
    source = source_name(path)
    key = f"{source}#{page}" if page is not None else source
    meta: dict[str, Any] = {"source": source, "title": path.stem, **metadata}
    if page is not None:
        meta["page"] = page
    return Document(id=hashlib.sha256(key.encode()).hexdigest()[:16], text=text, metadata=meta)
