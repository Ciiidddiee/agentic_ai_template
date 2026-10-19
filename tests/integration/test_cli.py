from __future__ import annotations

from typer.testing import CliRunner

from aikit.serving.cli import app

runner = CliRunner()


def invoke(index_path: str, *args: str) -> str:
    result = runner.invoke(
        app, ["--offline", "-s", f"components.vector_store.path={index_path}", *args]
    )
    assert result.exit_code == 0, result.output
    return result.output


def test_validate_ingest_ask(index_path: str) -> None:
    assert "config OK" in invoke(index_path, "validate")
    assert "documents" in invoke(index_path, "ingest")
    output = invoke(index_path, "ask", "How many days do I have to return an item?")
    assert "refund_policy.md" in output


def test_run_with_auto_approve(index_path: str) -> None:
    output = invoke(
        index_path, "run", "Please issue a refund for order A-1001, amount 80.", "--auto-approve"
    )
    assert "issue_refund" in output
    assert "refund_id" in output


def test_components_listing_and_schema(index_path: str) -> None:
    assert "check_refund_eligibility" in invoke(index_path, "components", "--kind", "tool")
    assert "chunk_overlap" in invoke(index_path, "components", "--schema", "chunker/markdown")


def test_bad_config_exits_with_code_2(tmp_path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("flow: {type: not_a_flow}\n", encoding="utf-8")
    result = runner.invoke(app, ["-c", str(bad), "validate"])
    assert result.exit_code == 2
