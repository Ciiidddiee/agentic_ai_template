"""Rename the kernel package after generating a project from the template.

    python scripts/rename_package.py acme_ai --dist acme-ai-kit --app-name acme-support

Renames src/aikit to src/<name>, rewrites imports, entry-point groups, the CLI
command, AIKIT_* environment variables, and the distribution name. Runs
automatically from `copier copy`; safe to run by hand on a fresh checkout.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

OLD = "aikit"
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".import_linter_cache",
    ".aikit",
    "node_modules",
    "dist",
    "build",
}
TEXT_SUFFIXES = {".py", ".toml", ".yaml", ".yml", ".md", ".cfg", ".ini", ".txt", ".jsonl", ".json"}
TEXT_NAMES = {"Dockerfile", ".importlinter", ".env.example", ".dockerignore", ".gitignore"}
# Copier owns this file; rewriting _src_path would break `copier update`.
SKIP_FILES = {".copier-answers.yml"}
IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")


def is_text(path: Path) -> bool:
    return path.suffix in TEXT_SUFFIXES or path.name in TEXT_NAMES


def iter_files(root: Path, skip: Path) -> list[Path]:
    files = []
    for path in root.rglob("*"):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if path.name in SKIP_FILES:
            continue
        if path.is_file() and is_text(path) and path.resolve() != skip:
            files.append(path)
    return files


def set_app_name(root: Path, app_name: str) -> None:
    app_yaml = root / "project" / "app.yaml"
    if not app_yaml.is_file():
        return
    text = app_yaml.read_text(encoding="utf-8")
    text = re.sub(r"(?m)^(app:\s*\n\s+name:\s*).*$", rf"\g<1>{app_name}", text, count=1)
    app_yaml.write_text(text, encoding="utf-8")


def rename(root: Path, new: str, dist: str) -> int:
    old_dir = root / "src" / OLD
    if new == OLD:
        return 0
    if not old_dir.is_dir():
        if (root / "src" / new).is_dir():
            print(f"Already renamed to {new}")
            return 0
        print(f"Cannot find {old_dir}", file=sys.stderr)
        return 1

    word = re.compile(rf"\b{OLD}\b")
    env = re.compile(rf"\b{OLD.upper()}_")
    changed = 0
    for path in iter_files(root, Path(__file__).resolve()):
        text = path.read_text(encoding="utf-8")
        updated = text
        if path.name == "pyproject.toml":
            updated = updated.replace(f'name = "{OLD}"', f'name = "{dist}"', 1)
            updated = updated.replace(f'"{OLD}[', f'"{dist}[')
        updated = env.sub(f"{new.upper()}_", word.sub(new, updated))
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            changed += 1

    old_dir.rename(root / "src" / new)
    print(f"Renamed package {OLD} -> {new} (distribution {dist}); updated {changed} files")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("name", help="New import name, e.g. acme_ai")
    parser.add_argument("--dist", help="Distribution name for pip (default: name with dashes)")
    parser.add_argument("--app-name", help="Value for app.name in project/app.yaml")
    parser.add_argument("--root", default=".", help="Project root (default: current directory)")
    args = parser.parse_args(argv)

    if not IDENTIFIER.match(args.name):
        parser.error("name must be a lowercase Python identifier, e.g. acme_ai")
    root = Path(args.root).resolve()
    status = rename(root, args.name, args.dist or args.name.replace("_", "-"))
    if status == 0 and args.app_name:
        set_app_name(root, args.app_name)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
