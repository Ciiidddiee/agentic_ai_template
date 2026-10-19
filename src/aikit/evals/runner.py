"""Runs eval datasets against the active flow.

Dataset rows (JSONL), RAG:
    {"id": "...", "question": "...", "expected_sources": ["refund_policy.md"],
     "forbidden_sources": [], "must_include": ["30 days"], "k": 5, "groups": []}
Agent:
    {"id": "...", "input": "...", "expected_tools": ["check_refund_eligibility"],
     "forbidden_tools": [], "must_include": ["eligible"], "expected_status": "completed"}
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from statistics import fmean
from typing import Any, Literal

from pydantic import BaseModel, Field

from aikit.core.config import EvalDataset
from aikit.core.context import RunContext
from aikit.core.errors import ConfigError
from aikit.core.ports import LLM
from aikit.core.types import RunEvent, RunResult
from aikit.evals import agent_metrics, rag_metrics
from aikit.runtime import Runtime

Kind = Literal["rag", "agent"]


class CaseResult(BaseModel):
    id: str
    kind: Kind
    input: str
    status: str
    answer: str
    passed: bool
    metrics: dict[str, float | None] = Field(default_factory=dict)
    tools_called: list[str] = Field(default_factory=list)
    retrieved_sources: list[str | None] = Field(default_factory=list)
    steps: int = 0
    total_tokens: int = 0


class EvalReport(BaseModel):
    app: str
    started_at: str
    cases: list[CaseResult]
    summary: dict[str, dict[str, float | None]]
    path: str | None = None


@dataclass
class _Observed:
    retrieved: list[str | None] = field(default_factory=list)
    contexts: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)


def load_dataset(path: str | Path) -> list[dict[str, Any]]:
    file = Path(path)
    if not file.is_file():
        raise ConfigError(f"Eval dataset not found: {file}")
    rows = []
    for number, line in enumerate(file.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("//"):
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ConfigError(f"{file}:{number}: invalid JSON: {exc}") from exc
    return rows


def detect_kind(case: dict[str, Any], declared: Kind | None) -> Kind:
    if declared:
        return declared
    return "rag" if "question" in case else "agent"


async def _consume(events: AsyncIterator[RunEvent], observed: _Observed) -> RunResult:
    result: dict[str, Any] | None = None
    async for item in events:
        if item.type == "retrieval":
            for chunk in item.data.get("chunks", []):
                observed.retrieved.append(chunk.get("source"))
                observed.contexts.append(chunk.get("text", ""))
        elif item.type == "tool_call":
            observed.tools.append(item.data.get("name", ""))
        elif item.type == "tool_result":
            observed.retrieved.extend(item.data.get("sources", []))
            if not item.data.get("is_error"):
                observed.contexts.append(item.data.get("content", ""))
        elif item.type == "done":
            result = item.data["result"]
    if result is None:
        raise RuntimeError("Flow finished without a result")
    return RunResult.model_validate(result)


async def run_case(
    runtime: Runtime,
    case: dict[str, Any],
    kind: Kind,
    *,
    judge: LLM | None,
    auto_approve: bool,
    index: int,
) -> CaseResult:
    text = str(case.get("question") or case.get("input") or "")
    ctx = RunContext(groups=list(case.get("groups", [])), metadata={"eval": True})
    observed = _Observed()
    result = await _consume(runtime.flow.stream(text, ctx), observed)
    resume = getattr(runtime.flow, "resume_stream", None)
    while result.status == "awaiting_approval" and auto_approve and resume is not None:
        result = await _consume(resume(result.run_id, True), observed)

    metrics: dict[str, float | None] = {}
    expected_status = case.get("expected_status", "completed")
    must_include = case.get("must_include", [])
    if kind == "rag":
        expected = case.get("expected_sources", [])
        cited = [c.source for c in result.citations]
        metrics["recall_at_k"] = rag_metrics.recall_at_k(
            observed.retrieved, expected, int(case.get("k", 5))
        )
        metrics["citation_precision"] = rag_metrics.citation_precision(cited, expected)
        metrics["keyword_coverage"] = rag_metrics.keyword_coverage(result.answer, must_include)
        if judge is not None:
            metrics["faithfulness"] = await rag_metrics.faithfulness(
                judge, text, result.answer, observed.contexts
            )
        forbidden = case.get("forbidden_sources", [])
        if forbidden:
            leaked = any(
                rag_metrics.source_matches(s, f) for s in observed.retrieved for f in forbidden
            )
            metrics["acl_leak"] = 1.0 if leaked else 0.0
        min_recall = float(case.get("min_recall", 1.0))
        passed = (
            result.status == expected_status
            and (metrics["recall_at_k"] is None or metrics["recall_at_k"] >= min_recall)
            and metrics["keyword_coverage"] in (None, 1.0)
            and metrics.get("acl_leak") in (None, 0.0)
        )
    else:
        expected_tools = case.get("expected_tools", [])
        metrics["tool_recall"] = agent_metrics.tool_recall(observed.tools, expected_tools)
        metrics["tool_precision"] = agent_metrics.tool_precision(observed.tools, expected_tools)
        metrics["keyword_coverage"] = rag_metrics.keyword_coverage(result.answer, must_include)
        passed = agent_metrics.task_success(
            status=result.status,
            expected_status=expected_status,
            answer=result.answer,
            must_include=must_include,
            called=observed.tools,
            expected_tools=expected_tools,
            forbidden_tools=case.get("forbidden_tools", []),
        )

    return CaseResult(
        id=str(case.get("id", f"case-{index}")),
        kind=kind,
        input=text,
        status=result.status,
        answer=result.answer,
        passed=passed,
        metrics=metrics,
        tools_called=observed.tools,
        retrieved_sources=observed.retrieved,
        steps=result.steps,
        total_tokens=result.usage.total_tokens,
    )


def summarize(cases: Sequence[CaseResult]) -> dict[str, dict[str, float | None]]:
    summary: dict[str, dict[str, float | None]] = {}
    for kind in ("rag", "agent"):
        group = [c for c in cases if c.kind == kind]
        if not group:
            continue
        stats: dict[str, float | None] = {
            "cases": float(len(group)),
            "pass_rate": sum(c.passed for c in group) / len(group),
            "avg_steps": fmean(c.steps for c in group),
            "avg_tokens": fmean(c.total_tokens for c in group),
        }
        names = sorted({name for c in group for name in c.metrics})
        for name in names:
            values = [c.metrics[name] for c in group if c.metrics.get(name) is not None]
            stats[name] = fmean(v for v in values if v is not None) if values else None
        summary[kind] = stats
    return summary


async def run_evals(
    runtime: Runtime,
    datasets: Sequence[EvalDataset] | None = None,
    *,
    auto_approve: bool | None = None,
    output_dir: str | None = None,
    write: bool = True,
) -> EvalReport:
    section = runtime.config.evals
    datasets = list(datasets or section.datasets)
    if not datasets:
        raise ConfigError("No eval datasets: add evals.datasets to the config or pass --dataset")
    approve = section.auto_approve if auto_approve is None else auto_approve
    judge: LLM | None = None
    if section.judge:
        judge = runtime.component(section.judge.removeprefix("@"))

    started = datetime.now(UTC)
    cases: list[CaseResult] = []
    for dataset in datasets:
        for case in load_dataset(dataset.path):
            kind = detect_kind(case, dataset.kind)
            cases.append(
                await run_case(
                    runtime, case, kind, judge=judge, auto_approve=approve, index=len(cases) + 1
                )
            )

    report = EvalReport(
        app=runtime.config.app.name,
        started_at=started.isoformat(),
        cases=cases,
        summary=summarize(cases),
    )
    if write:
        directory = Path(output_dir or section.output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"eval-{started.strftime('%Y%m%d-%H%M%S')}.json"
        report.path = path.as_posix()
        path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return report
