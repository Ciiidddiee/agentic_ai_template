from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.rename_package import OLD, main

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(
    not (ROOT / "src" / OLD).is_dir(), reason="package already renamed in this project"
)
def test_rename_produces_an_importable_package(tmp_path: Path) -> None:
    for item in ("src", "project", "pyproject.toml", ".importlinter", ".env.example"):
        source = ROOT / item
        if source.is_dir():
            shutil.copytree(source, tmp_path / item, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(source, tmp_path / item)
    answers = tmp_path / ".copier-answers.yml"
    answers.write_text(f"_src_path: /templates/{OLD}-template\n", encoding="utf-8")

    assert main(["acme_ai", "--root", str(tmp_path), "--app-name", "acme-demo"]) == 0

    assert (tmp_path / "src" / "acme_ai").is_dir()
    assert not (tmp_path / "src" / OLD).exists()
    pyproject = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "acme-ai"' in pyproject
    assert '"acme-ai[api,loaders]"' in pyproject
    assert 'acme_ai = "acme_ai.serving.cli:app"' in pyproject
    assert "ACME_AI_CONFIG" in (tmp_path / ".env.example").read_text(encoding="utf-8")
    assert "name: acme-demo" in (tmp_path / "project" / "app.yaml").read_text(encoding="utf-8")
    leftovers = [
        p for p in (tmp_path / "src").rglob("*.py") if OLD in p.read_text(encoding="utf-8")
    ]
    assert not leftovers
    assert answers.read_text(encoding="utf-8") == f"_src_path: /templates/{OLD}-template\n"

    check = subprocess.run(
        [sys.executable, "-c", "import acme_ai.runtime, project.tools; print('ok')"],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(tmp_path / "src")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert check.returncode == 0, check.stderr


def test_invalid_name_rejected() -> None:
    try:
        main(["Acme-AI"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("expected argparse to reject the name")
