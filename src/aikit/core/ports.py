"""Interfaces every component implements. Flows depend only on these."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol, runtime_checkable

from aikit.core.context import RunContext
from aikit.core.types import (
    Chunk,
    Document,
    LLMResponse,
    Message,
    RunEvent,
    RunResult,
    ScoredChunk,
    ToolResult,
    ToolSpec,
)


@runtime_checkable
class LLM(Protocol):
    model: str

    async def chat(
        self,
        messages: list[Message],
        *,
        tools: list[ToolSpec] | None = None,
        **options: Any,
    ) -> LLMResponse: ...

    def stream(self, messages: list[Message], **options: Any) -> AsyncIterator[str]: ...


@runtime_checkable
class Embedder(Protocol):
    model: str

    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...


@runtime_checkable
class VectorStore(Protocol):
    async def upsert(self, chunks: list[Chunk]) -> None: ...

    async def search(
        self,
        vector: list[float],
        *,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
        groups: list[str] | None = None,
    ) -> list[ScoredChunk]: ...

    async def delete(self, ids: list[str]) -> None: ...

    async def ids(self, filters: dict[str, Any] | None = None) -> set[str]: ...

    async def count(self) -> int: ...


@runtime_checkable
class KeywordSearchable(Protocol):
    """Optional capability for stores that also support lexical (BM25-style) search."""

    async def keyword_search(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
        groups: list[str] | None = None,
    ) -> list[ScoredChunk]: ...


@runtime_checkable
class Loader(Protocol):
    async def load(self) -> list[Document]: ...


@runtime_checkable
class Chunker(Protocol):
    def split(self, document: Document) -> list[Chunk]: ...


@runtime_checkable
class Retriever(Protocol):
    async def retrieve(
        self,
        query: str,
        *,
        top_k: int | None = None,
        filters: dict[str, Any] | None = None,
        groups: list[str] | None = None,
    ) -> list[ScoredChunk]: ...


@runtime_checkable
class Reranker(Protocol):
    async def rerank(self, query: str, chunks: list[ScoredChunk]) -> list[ScoredChunk]: ...


@runtime_checkable
class Memory(Protocol):
    async def load(self, session_id: str) -> list[Message]: ...

    async def save(self, session_id: str, messages: list[Message]) -> None: ...


@runtime_checkable
class Tool(Protocol):
    spec: ToolSpec

    async def run(self, args: dict[str, Any], ctx: RunContext) -> ToolResult: ...


@runtime_checkable
class Guardrail(Protocol):
    """Checks or rewrites text at one or more stages: input, context, tool_result, output.

    Raise `GuardrailViolationError` to block; return (possibly modified) text to allow.
    """

    name: str
    stages: frozenset[str]

    async def apply(self, text: str, *, stage: str, ctx: RunContext) -> str: ...


@runtime_checkable
class RunStore(Protocol):
    """Persists paused agent runs so they can resume after human approval."""

    async def save(self, run_id: str, state: dict[str, Any]) -> None: ...

    async def load(self, run_id: str) -> dict[str, Any] | None: ...

    async def delete(self, run_id: str) -> None: ...


@runtime_checkable
class QueryFlow(Protocol):
    """A flow that answers an input: RAG, agent, or a custom workflow."""

    def stream(self, input: str, ctx: RunContext | None = None) -> AsyncIterator[RunEvent]: ...

    async def run(self, input: str, ctx: RunContext | None = None) -> RunResult: ...


KIND_BY_PORT: dict[type, str] = {
    LLM: "llm",
    Embedder: "embedder",
    VectorStore: "vector_store",
    Loader: "loader",
    Chunker: "chunker",
    Retriever: "retriever",
    Reranker: "reranker",
    Memory: "memory",
    Tool: "tool",
    Guardrail: "guardrail",
    RunStore: "run_store",
}
