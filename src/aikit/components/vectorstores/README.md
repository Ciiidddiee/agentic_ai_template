# components/vectorstores

Vector stores. They implement `VectorStore`: `upsert`, `search(vector, top_k, filters, groups)`, `delete`, `ids(filters)`, and `count`. Stores can optionally also implement `KeywordSearchable.keyword_search`, which the `hybrid` retriever uses.

| Type | File | Use |
|---|---|---|
| `in_memory` | `in_memory.py` | Brute-force cosine search plus BM25 keyword search, persisted as JSON at `path` with atomic writes. Fine for prototypes and up to tens of thousands of chunks. |

Requirements for every store:

- **Enforce ACLs inside `search`**, using `groups` and chunk `metadata.acl` (see `core/filters.acl_allows`). Never filter after the store returns results.
- **Make `upsert` idempotent by chunk id.** Ingest relies on this.
- Pass `VectorStoreContract` in `tests/contract/test_vector_store_contract.py`.

Production stores (pgvector, Qdrant, OpenSearch, ...) can live here or in a plugin package. See [docs/adding_components.md](../../../../docs/adding_components.md).
