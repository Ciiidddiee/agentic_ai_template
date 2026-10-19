from __future__ import annotations

from pathlib import Path

from aikit.components.loaders.markdown import MarkdownLoader
from aikit.components.loaders.text import TextLoader


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


async def test_folder_docs_are_not_ingested(tmp_path: Path) -> None:
    write(tmp_path / "policy.md", "---\nacl: [hr]\n---\n# Policy\nbody")
    write(tmp_path / "README.md", "# Folder docs")
    write(tmp_path / "nested" / "AGENTS.md", "# AI context")

    documents = await MarkdownLoader(path=str(tmp_path)).load()

    assert [d.metadata["title"] for d in documents] == ["policy"]
    assert documents[0].metadata["acl"] == ["hr"]


async def test_exclude_can_be_overridden(tmp_path: Path) -> None:
    write(tmp_path / "README.md", "# Folder docs")
    write(tmp_path / "notes.txt", "keep")
    write(tmp_path / "draft-notes.txt", "skip")

    assert len(await MarkdownLoader(path=str(tmp_path), exclude=[]).load()) == 1
    texts = await TextLoader(path=str(tmp_path), exclude=["draft-*"]).load()
    assert [d.text for d in texts] == ["keep"]
