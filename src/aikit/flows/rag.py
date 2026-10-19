from __future__ import annotations

import re
from collections.abc import AsyncIterator
from typing import Any

from aikit.core.context import RunContext
from aikit.core.hooks import Hook
from aikit.core.ports import LLM, Guardrail, Memory, Reranker, Retriever
from aikit.core.prompts import load_prompt, render
from aikit.core.registry import register
from aikit.core.types import Citation, LLMResponse, Message, RunEvent, ScoredChunk
from aikit.flows.base import BaseFlow, event

DEFAULT_SYSTEM_PROMPT = (
    "Answer the question using only the numbered context passages. "
    "Cite passages inline like [1]. If the context does not contain the answer, say so."
)
DEFAULT_USER_TEMPLATE = "Context:\n{context}\n\nQuestion: {question}"
REWRITE_PROMPT = (
    "Rewrite the user's last message as a standalone search query, using the "
    "conversation for context. Reply with the query only."
)
_CITATION = re.compile(r"\[(\d+)\]")


@register("flow", "rag")
class RagFlow(BaseFlow):
    """Retrieve -> (rerank) -> generate an answer with numbered citations.

    Tokens stream as they arrive unless an output guardrail is configured, in
    which case the answer is buffered so the guardrail sees it before the user.
    """

    def __init__(
        self,
        llm: LLM,
        retriever: Retriever,
        prompt: str = DEFAULT_SYSTEM_PROMPT,
        user_template: str = DEFAULT_USER_TEMPLATE,
        reranker: Reranker | None = None,
        memory: Memory | None = None,
        top_k: int = 8,
        filters: dict[str, Any] | None = None,
        min_score: float | None = None,
        rewrite_query: bool = False,
        stream_tokens: bool = True,
        require_citations: bool = True,
        no_answer_text: str = "I couldn't find this in the available documents.",
        llm_options: dict[str, Any] | None = None,
        guardrails: list[Guardrail] | None = None,
        hooks: list[Hook] | None = None,
    ) -> None:
        super().__init__(guardrails, hooks)
        self.llm = llm
        self.retriever = retriever
        self.prompt = load_prompt(prompt)
        self.user_template = load_prompt(user_template)
        self.reranker = reranker
        self.memory = memory
        self.top_k = top_k
        self.filters = filters or {}
        self.min_score = min_score
        self.rewrite_query = rewrite_query
        self.stream_tokens = stream_tokens
        self.require_citations = require_citations
        self.no_answer_text = no_answer_text
        self.llm_options = llm_options or {}

    async def _events(self, input: str, ctx: RunContext) -> AsyncIterator[RunEvent]:
        question = await self.hooks.on_input(input, ctx)
        history = await self.memory.load(ctx.session_id) if self.memory and ctx.session_id else []
        query = question
        if self.rewrite_query and history:
            query = await self._rewrite(question, history, ctx)

        results = await self.retriever.retrieve(
            query, top_k=self.top_k, filters=self.filters or None, groups=ctx.groups
        )
        results = await self.hooks.after_retrieve(query, results, ctx)
        if self.reranker and results:
            results = await self.reranker.rerank(query, results)
        yield event("retrieval", query=query, chunks=[_summary(r) for r in results])

        best = max((r.score for r in results), default=0.0)
        if not results or (self.min_score is not None and best < self.min_score):
            yield event("answer", text=self.no_answer_text, citations=[])
            yield self._done(
                self._result(
                    ctx, "completed", answer=self.no_answer_text, metadata={"no_answer": True}
                )
            )
            return

        messages = [
            Message.system(self.prompt),
            *history,
            Message.user(
                render(self.user_template, context=format_context(results), question=question)
            ),
        ]
        messages = await self.hooks.before_llm(messages, ctx)

        if self.stream_tokens and not self.has_output_guardrails:
            parts: list[str] = []
            async for token in self.llm.stream(messages, **self.llm_options):
                parts.append(token)
                yield event("token", text=token)
            response = LLMResponse(content="".join(parts), model=self.llm.model)
        else:
            response = await self.llm.chat(messages, **self.llm_options)
        ctx.usage.add(response.usage)
        response = await self.hooks.after_llm(response, ctx)

        answer = await self.hooks.on_answer(response.content or "", ctx)
        citations = extract_citations(answer, results)
        if self.memory and ctx.session_id:
            await self.memory.save(
                ctx.session_id, [*history, Message.user(question), Message.assistant(answer)]
            )

        cited = [c.model_dump() for c in citations]
        yield event("answer", text=answer, citations=cited)
        yield self._done(
            self._result(
                ctx,
                "completed",
                answer=answer,
                citations=citations,
                steps=1,
                metadata={"citations_missing": self.require_citations and not citations},
            )
        )

    async def _rewrite(self, question: str, history: list[Message], ctx: RunContext) -> str:
        transcript = "\n".join(f"{m.role}: {m.content}" for m in history if m.content)
        response = await self.llm.chat(
            [
                Message.system(REWRITE_PROMPT),
                Message.user(f"{transcript}\nuser: {question}"),
            ],
            temperature=0,
        )
        ctx.usage.add(response.usage)
        return (response.content or "").strip() or question


def format_context(results: list[ScoredChunk]) -> str:
    blocks = []
    for i, item in enumerate(results, start=1):
        meta = item.chunk.metadata
        label = str(meta.get("source", "unknown"))
        if meta.get("page"):
            label += f", page {meta['page']}"
        if meta.get("section"):
            label += f", {meta['section']}"
        blocks.append(f"[{i}] ({label})\n{item.chunk.text}")
    return "\n\n".join(blocks)


def extract_citations(answer: str, results: list[ScoredChunk]) -> list[Citation]:
    citations: list[Citation] = []
    seen: set[int] = set()
    for match in _CITATION.finditer(answer):
        index = int(match.group(1))
        if index in seen or not 1 <= index <= len(results):
            continue
        seen.add(index)
        chunk = results[index - 1].chunk
        citations.append(
            Citation(
                index=index,
                chunk_id=chunk.id,
                source=chunk.metadata.get("source"),
                page=chunk.metadata.get("page"),
                snippet=chunk.text[:200],
            )
        )
    return citations


def _summary(item: ScoredChunk) -> dict[str, Any]:
    meta = item.chunk.metadata
    return {
        "id": item.chunk.id,
        "source": meta.get("source"),
        "page": meta.get("page"),
        "section": meta.get("section"),
        "score": round(item.score, 4),
        "text": item.chunk.text[:200],
    }
