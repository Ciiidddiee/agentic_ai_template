# components/rerankers

These reorder retrieved chunks. Each implements `Reranker`: `rerank(query, chunks) -> list[ScoredChunk]`. Set how many chunks to keep with the `top_n` constructor parameter.

| Type | File | Notes |
|---|---|---|
| `passthrough` | `passthrough.py` | Keeps the retriever's order and truncates to `top_n` |
| `llm_rerank` | `llm_rerank.py` | Asks an LLM to score relevance as JSON. If the response can't be parsed, it falls back to the original order. |

A cross-encoder or a gateway `/rerank` endpoint would be a natural addition here.
