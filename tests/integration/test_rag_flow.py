from __future__ import annotations

from collections.abc import Callable

from aikit.core.context import RunContext
from aikit.core.types import RunEvent
from aikit.runtime import Runtime

PROFILE = "project/profiles/rag.yaml"


async def ingest(runtime: Runtime) -> None:
    assert runtime.ingest is not None
    report = await runtime.ingest.run()
    assert report.documents == 4 and report.embedded == report.chunks > 0


async def events(runtime: Runtime, question: str, ctx: RunContext | None = None) -> list[RunEvent]:
    return [e async for e in runtime.flow.stream(question, ctx)]


async def test_answer_with_citations(offline_runtime: Callable[..., Runtime]) -> None:
    runtime = offline_runtime(PROFILE)
    await ingest(runtime)
    result = await runtime.flow.run("Is there a restocking fee for opened items?")
    assert result.status == "completed"
    assert "Opened items" in result.answer
    assert result.citations and result.citations[0].source.endswith("refund_policy.md")
    assert result.metadata["citations_missing"] is False


async def test_reingest_is_idempotent(offline_runtime: Callable[..., Runtime]) -> None:
    runtime = offline_runtime(PROFILE)
    await ingest(runtime)
    assert runtime.ingest is not None
    again = await runtime.ingest.run()
    assert again.embedded == 0 and again.unchanged == again.chunks


async def test_tokens_stream_and_events_are_ordered(
    offline_runtime: Callable[..., Runtime],
) -> None:
    runtime = offline_runtime(PROFILE)
    await ingest(runtime)
    types = [e.type for e in await events(runtime, "How long is the warranty?")]
    assert types[0] == "start" and types[-1] == "done"
    assert types.index("retrieval") < types.index("token") < types.index("answer")


async def test_acl_filters_restricted_documents(offline_runtime: Callable[..., Runtime]) -> None:
    runtime = offline_runtime(PROFILE)
    await ingest(runtime)
    question = "What goodwill credit can support leads grant?"

    def sources(evts: list[RunEvent]) -> set[str]:
        retrieval = next(e for e in evts if e.type == "retrieval")
        return {c["source"] for c in retrieval.data["chunks"]}

    public = sources(await events(runtime, question, RunContext(groups=[])))
    leads = sources(await events(runtime, question, RunContext(groups=["support_leads"])))
    assert not any(s.endswith("internal_escalation.md") for s in public)
    assert any(s.endswith("internal_escalation.md") for s in leads)


async def test_no_answer_below_min_score(offline_runtime: Callable[..., Runtime]) -> None:
    runtime = offline_runtime(PROFILE, **{"flow.min_score": 0.99})
    await ingest(runtime)
    result = await runtime.flow.run("Tell me about quantum chromodynamics")
    assert result.metadata["no_answer"] is True
    assert "couldn't find" in result.answer


async def test_output_guardrail_buffers_the_answer(offline_runtime: Callable[..., Runtime]) -> None:
    runtime = offline_runtime(
        PROFILE, **{"flow.guardrails": [{"type": "pii_redact", "stages": ["output"]}]}
    )
    await ingest(runtime)
    types = [e.type for e in await events(runtime, "How long is the warranty?")]
    assert "token" not in types and "answer" in types


async def test_input_guardrail_blocks(offline_runtime: Callable[..., Runtime]) -> None:
    runtime = offline_runtime(PROFILE)
    result = await runtime.flow.run("x" * 5000)
    assert result.status == "blocked"
    assert result.metadata["guardrail"] == "max_length"
