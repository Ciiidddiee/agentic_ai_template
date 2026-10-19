from __future__ import annotations

from collections.abc import Sequence

from aikit.evals.rag_metrics import keyword_coverage


def tool_recall(called: Sequence[str], expected: Sequence[str]) -> float | None:
    """Share of expected tools the agent actually called."""
    if not expected:
        return None
    return sum(1 for name in expected if name in called) / len(expected)


def tool_precision(called: Sequence[str], expected: Sequence[str]) -> float | None:
    """Share of called tools that were expected. Low values mean wasted or risky calls."""
    if not called or not expected:
        return None
    return sum(1 for name in called if name in expected) / len(called)


def task_success(
    *,
    status: str,
    expected_status: str,
    answer: str,
    must_include: Sequence[str],
    called: Sequence[str],
    expected_tools: Sequence[str],
    forbidden_tools: Sequence[str] = (),
) -> bool:
    if status != expected_status:
        return False
    if any(name in called for name in forbidden_tools):
        return False
    recall = tool_recall(called, expected_tools)
    if recall is not None and recall < 1.0:
        return False
    coverage = keyword_coverage(answer, must_include)
    return coverage is None or coverage == 1.0
