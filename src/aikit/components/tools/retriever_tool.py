from __future__ import annotations

from typing import Any

from aikit.core.context import RunContext
from aikit.core.ports import Retriever
from aikit.core.registry import register
from aikit.core.tooling import BaseTool
from aikit.core.types import Citation, ToolResult, ToolSpec


@register("tool", "retriever_tool")
class RetrieverTool(BaseTool):
    """Exposes a retriever to an agent. This is what turns an agent into agentic RAG.

    Results respect the caller's ACL groups from the RunContext, and carry
    citations the agent flow collects into the final result.
    """

    def __init__(
        self,
        retriever: Retriever,
        name: str = "search_documents",
        description: str = "Search the knowledge base and return relevant passages with sources.",
        top_k: int = 5,
        max_chars_per_chunk: int = 800,
    ) -> None:
        self.retriever = retriever
        self.top_k = top_k
        self.max_chars = max_chars_per_chunk
        self.spec = ToolSpec(
            name=name,
            description=description,
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to search for"},
                },
                "required": ["query"],
            },
            capabilities=frozenset({"read"}),
        )

    async def run(self, args: dict[str, Any], ctx: RunContext) -> ToolResult:
        query = str(args.get("query", "")).strip()
        if not query:
            return ToolResult(content="Provide a non-empty 'query'.", is_error=True)
        results = await self.retriever.retrieve(query, top_k=self.top_k, groups=ctx.groups)
        if not results:
            return ToolResult(content="No relevant documents found.", data={"citations": []})
        blocks: list[str] = []
        citations: list[dict[str, Any]] = []
        for i, item in enumerate(results, start=1):
            meta = item.chunk.metadata
            source = meta.get("source")
            page = meta.get("page")
            label = f"{source}, page {page}" if page else f"{source}"
            blocks.append(f"[{i}] ({label})\n{item.chunk.text[: self.max_chars]}")
            citations.append(
                Citation(
                    index=i,
                    chunk_id=item.chunk.id,
                    source=source,
                    page=page,
                    snippet=item.chunk.text[:200],
                ).model_dump()
            )
        return ToolResult(content="\n\n".join(blocks), data={"citations": citations})
