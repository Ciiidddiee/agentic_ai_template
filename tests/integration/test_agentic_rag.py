from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from aikit.evals import run_evals
from aikit.runtime import Runtime


async def test_agent_searches_documents_and_cites(offline_runtime: Callable[..., Runtime]) -> None:
    runtime = offline_runtime("project/app.yaml")
    assert runtime.ingest is not None
    await runtime.ingest.run()
    result = await runtime.flow.run("How many days do I have to return an item for a refund?")
    assert result.status == "completed"
    assert [c.name for c in result.tool_calls] == ["search_policies"]
    assert any(c.source and c.source.endswith("refund_policy.md") for c in result.citations)
    assert "30 days" in result.answer


async def test_domain_tool_through_agent(offline_runtime: Callable[..., Runtime]) -> None:
    runtime = offline_runtime("project/profiles/agent.yaml")
    result = await runtime.flow.run(
        "Can I get a refund? My order total was 120 and I bought it 10 days ago."
    )
    assert [c.name for c in result.tool_calls] == ["check_refund_eligibility"]
    assert '"eligible": true' in result.answer


async def test_eval_suite_passes_offline(
    offline_runtime: Callable[..., Runtime], tmp_path: Path
) -> None:
    runtime = offline_runtime("project/app.yaml")
    assert runtime.ingest is not None
    await runtime.ingest.run()
    report = await run_evals(runtime, output_dir=str(tmp_path))
    failed = [c.id for c in report.cases if not c.passed]
    assert not failed, failed
    assert report.summary["rag"]["recall_at_k"] == 1.0
    assert report.summary["rag"]["acl_leak"] == 0.0
    assert report.path and Path(report.path).is_file()
