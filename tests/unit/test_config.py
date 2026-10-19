from __future__ import annotations

from pathlib import Path

import pytest

from aikit.core.config import apply_overrides, deep_merge, load_config, make_offline
from aikit.core.errors import ConfigError


def write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_env_interpolation_with_defaults(tmp_path: Path) -> None:
    cfg = write(
        tmp_path / "app.yaml",
        "components:\n  llm: {type: fake, model: '${MODEL:-small}'}\nflow: {type: rag, top_k: '${TOP_K}'}\n",
    )
    config = load_config(cfg, env={"TOP_K": "3"})
    assert config.components["llm"]["model"] == "small"
    assert config.flow["top_k"] == "3"


def test_missing_env_vars_are_listed(tmp_path: Path) -> None:
    cfg = write(tmp_path / "app.yaml", "flow: {type: rag, url: '${A}/${B}'}\n")
    with pytest.raises(ConfigError, match="A, B"):
        load_config(cfg, env={})


def test_extends_merges_and_type_change_replaces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    write(
        tmp_path / "base.yaml",
        "components:\n  llm: {type: openai_compat, base_url: x, model: y}\n"
        "  store: {kind: vector_store, type: in_memory, path: a.json}\n"
        "flow: {type: rag, top_k: 8, min_score: 0.2}\n",
    )
    write(
        tmp_path / "child.yaml",
        "extends: base.yaml\ncomponents:\n  llm: {type: fake}\n  store: {path: b.json}\n"
        "flow: {top_k: 3, min_score: null}\n",
    )
    config = load_config("child.yaml", env={})
    assert config.components["llm"] == {"type": "fake"}
    assert config.components["store"] == {
        "kind": "vector_store",
        "type": "in_memory",
        "path": "b.json",
    }
    assert config.flow == {"type": "rag", "top_k": 3}


def test_circular_extends(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    write(tmp_path / "a.yaml", "extends: b.yaml\nflow: {type: rag}\n")
    write(tmp_path / "b.yaml", "extends: a.yaml\n")
    with pytest.raises(ConfigError, match="Circular"):
        load_config("a.yaml", env={})


def test_overrides_from_cli_strings_and_dicts() -> None:
    raw = {"flow": {"type": "rag", "top_k": 8}}
    assert apply_overrides(raw, ["flow.top_k=3", "flow.filters={tag: a}"])["flow"] == {
        "type": "rag",
        "top_k": 3,
        "filters": {"tag": "a"},
    }
    assert apply_overrides(raw, {"components.llm.type": "fake"})["components"] == {
        "llm": {"type": "fake"}
    }
    with pytest.raises(ConfigError):
        apply_overrides(raw, ["no-equals-sign"])


def test_offline_swaps_llms_and_embedders_only() -> None:
    raw = {
        "components": {
            "llm": {"type": "openai_compat", "base_url": "${URL}"},
            "judge": {"kind": "llm", "type": "openai_compat"},
            "embedder": {"type": "openai_compat"},
            "vector_store": {"type": "in_memory"},
        }
    }
    swapped = make_offline(raw)["components"]
    assert swapped["llm"] == {"type": "fake"}
    assert swapped["judge"] == {"type": "fake", "kind": "llm"}
    assert swapped["embedder"] == {"type": "fake"}
    assert swapped["vector_store"] == {"type": "in_memory"}


def test_offline_happens_before_env_interpolation(tmp_path: Path) -> None:
    cfg = write(
        tmp_path / "app.yaml",
        "components:\n  llm: {type: openai_compat, base_url: '${LLM_BASE_URL}', model: m}\nflow: {type: rag}\n",
    )
    config = load_config(cfg, offline=True, env={})
    assert config.components["llm"] == {"type": "fake"}


def test_unknown_top_level_keys_rejected(tmp_path: Path) -> None:
    cfg = write(tmp_path / "app.yaml", "flow: {type: rag}\nflwo: {}\n")
    with pytest.raises(ConfigError, match="flwo"):
        load_config(cfg, env={})


def test_deep_merge_does_not_mutate_inputs() -> None:
    base = {"a": {"b": 1}}
    deep_merge(base, {"a": {"c": 2}})
    assert base == {"a": {"b": 1}}


def test_project_profiles_all_load() -> None:
    for profile in ("rag", "agent", "agentic_rag"):
        config = load_config(f"project/profiles/{profile}.yaml", env={})
        assert config.flow["type"] in {"rag", "agent"}
