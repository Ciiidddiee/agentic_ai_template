from __future__ import annotations

import json
import re
from collections.abc import Sequence

from aikit.core.ports import LLM
from aikit.core.types import Message

JUDGE_PROMPT = (
    "You grade whether an answer is fully supported by the provided context. "
    'Respond with JSON only: {"score": <number from 0 to 1>, "reason": "<short reason>"}. '
    "1 means every claim is supported; "
    "0 means the answer is unsupported or contradicts the context."
)
_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


def source_matches(source: str | None, expected: str) -> bool:
    """`expected` may be a file name or a path suffix, e.g. `refund_policy.md`."""
    if not source:
        return False
    normalized = source.replace("\\", "/")
    target = expected.replace("\\", "/")
    return normalized == target or normalized.endswith("/" + target)


def recall_at_k(retrieved: Sequence[str | None], expected: Sequence[str], k: int) -> float | None:
    """Share of expected sources that appear in the top-k retrieved chunks."""
    if not expected:
        return None
    top = list(retrieved)[:k]
    hits = sum(1 for e in expected if any(source_matches(s, e) for s in top))
    return hits / len(expected)


def citation_precision(cited: Sequence[str | None], expected: Sequence[str]) -> float | None:
    """Share of cited sources that are among the expected sources."""
    if not cited or not expected:
        return None
    good = sum(1 for c in cited if any(source_matches(c, e) for e in expected))
    return good / len(cited)


def keyword_coverage(answer: str, must_include: Sequence[str]) -> float | None:
    if not must_include:
        return None
    lowered = answer.lower()
    return sum(1 for word in must_include if word.lower() in lowered) / len(must_include)


async def faithfulness(
    judge: LLM, question: str, answer: str, contexts: Sequence[str]
) -> float | None:
    """LLM-as-judge groundedness score in [0, 1], or None if the judge reply is unusable."""
    if not answer.strip() or not contexts:
        return None
    context = "\n\n".join(f"- {c}" for c in contexts)
    response = await judge.chat(
        [
            Message.system(JUDGE_PROMPT),
            Message.user(f"Question: {question}\n\nContext:\n{context}\n\nAnswer: {answer}"),
        ],
        temperature=0,
    )
    match = _OBJECT.search(response.content or "")
    if not match:
        return None
    try:
        score = json.loads(match.group(0)).get("score")
    except (json.JSONDecodeError, AttributeError):
        return None
    if not isinstance(score, int | float):
        return None
    return max(0.0, min(1.0, float(score)))
