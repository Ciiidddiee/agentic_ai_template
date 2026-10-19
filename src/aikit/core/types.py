from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

Role = Literal["system", "user", "assistant", "tool"]

Capability = Literal["read", "write", "network", "pii", "code"]
"""What a tool can do. `write` and `code` make a tool non-read-only."""

RunStatus = Literal[
    "completed",
    "awaiting_approval",
    "max_steps",
    "budget_exceeded",
    "timeout",
    "blocked",
    "error",
]

EventType = Literal[
    "start",
    "status",
    "retrieval",
    "token",
    "tool_call",
    "tool_result",
    "approval_required",
    "answer",
    "error",
    "done",
]


def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:16]}"


class ToolCall(BaseModel):
    id: str = Field(default_factory=lambda: new_id("call_"))
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class Message(BaseModel):
    role: Role
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    name: str | None = None

    @classmethod
    def system(cls, content: str) -> Message:
        return cls(role="system", content=content)

    @classmethod
    def user(cls, content: str) -> Message:
        return cls(role="user", content=content)

    @classmethod
    def assistant(cls, content: str | None, tool_calls: list[ToolCall] | None = None) -> Message:
        return cls(role="assistant", content=content, tool_calls=tool_calls or None)

    @classmethod
    def tool(cls, call_id: str, content: str, name: str | None = None) -> Message:
        return cls(role="tool", content=content, tool_call_id=call_id, name=name)


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def add(self, other: Usage) -> None:
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens


class LLMResponse(BaseModel):
    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
    model: str | None = None
    finish_reason: str | None = None


class ToolSpec(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=lambda: {"type": "object", "properties": {}})
    capabilities: frozenset[Capability] = frozenset({"read"})
    requires_approval: bool = False

    @property
    def read_only(self) -> bool:
        return not ({"write", "code"} & set(self.capabilities))


class ToolResult(BaseModel):
    call_id: str = ""
    content: str
    data: dict[str, Any] = Field(default_factory=dict)
    is_error: bool = False


class Document(BaseModel):
    id: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class Chunk(BaseModel):
    """A retrievable piece of a document.

    Conventional metadata keys: source, page, section, acl, document_id,
    ingested_at, embedding_model.
    """

    id: str
    document_id: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    embedding: list[float] | None = None


class ScoredChunk(BaseModel):
    chunk: Chunk
    score: float


class Citation(BaseModel):
    index: int
    chunk_id: str
    source: str | None = None
    page: int | None = None
    snippet: str = ""


class RunResult(BaseModel):
    run_id: str
    status: RunStatus
    answer: str = ""
    citations: list[Citation] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
    steps: int = 0
    tool_calls: list[ToolCall] = Field(default_factory=list)
    pending_approvals: list[ToolCall] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunEvent(BaseModel):
    type: EventType
    run_id: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class IngestReport(BaseModel):
    documents: int = 0
    chunks: int = 0
    embedded: int = 0
    unchanged: int = 0
    deleted: int = 0
    duration_s: float = 0.0
