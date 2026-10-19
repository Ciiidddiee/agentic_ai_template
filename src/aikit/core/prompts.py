from __future__ import annotations

from pathlib import Path

from aikit.core.errors import ConfigError

PROMPT_SUFFIXES = (".md", ".txt", ".prompt")


def load_prompt(value: str) -> str:
    """Return the prompt text: read it from a file if `value` is a path, else use it inline.

    Paths are relative to the working directory (the repo root).
    """
    if value.strip().endswith(PROMPT_SUFFIXES) and "\n" not in value:
        path = Path(value.strip())
        if not path.is_file():
            raise ConfigError(f"Prompt file not found: {path}")
        return path.read_text(encoding="utf-8")
    return value


def render(template: str, **variables: object) -> str:
    """Replace `{name}` placeholders. Unknown braces (for example JSON examples) are left alone."""
    for name, value in variables.items():
        template = template.replace("{" + name + "}", str(value))
    return template
