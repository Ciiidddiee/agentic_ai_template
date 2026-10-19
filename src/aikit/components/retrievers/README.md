# components/retrievers

These turn a query into scored chunks. Each implements `Retriever`: `retrieve(query, top_k=None, filters=None, groups=None) -> list[ScoredChunk]`. Flows pass `RunContext.groups` as `groups`, so ACLs are enforced in the store.

| Type | File | Notes |
|---|---|---|
| `dense` | `dense.py` | Embeds the query and runs vector search |
| `hybrid` | `hybrid.py` | Weighted reciprocal-rank fusion of vector and BM25 results (`alpha` is the vector weight). Needs a store that implements `KeywordSearchable`; with any other store it fails at startup. Reported scores are cosine similarities, so `min_score` keeps its meaning. |

The RAG flow uses retrievers directly. Agents use them through the `retriever_tool`.
