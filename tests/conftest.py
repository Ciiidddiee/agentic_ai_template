from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from aikit.runtime import Runtime, load_runtime

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _repo_root(monkeypatch: pytest.MonkeyPatch) -> None:
    """Config paths are relative to the repo root, so every test runs from there."""
    monkeypatch.chdir(ROOT)
    for name in ("AIKIT_CONFIG", "AIKIT_OFFLINE", "LLM_BASE_URL", "LLM_MODEL", "LLM_TOKEN"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def index_path(tmp_path: Path) -> str:
    return str(tmp_path / "index.json")


@pytest.fixture
def offline_runtime(index_path: str) -> Callable[..., Runtime]:
    """Build a runtime for a profile with fakes and a throwaway index."""

    def make(config: str = "project/app.yaml", **overrides: Any) -> Runtime:
        return load_runtime(
            config,
            overrides={"components.vector_store.path": index_path, **overrides},
            offline=True,
            env_file=None,
            log_level="WARNING",
        )

    return make
