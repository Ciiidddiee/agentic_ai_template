# components/embeddings

Text embedders. They implement `Embedder`: `embed(texts)` and `embed_query(text)`.

| Type | File | Use |
|---|---|---|
| `openai_compat` | `openai_compat.py` | `/v1/embeddings` gateways. Supports `batch_size`, `dimensions`, and `query_prefix` / `document_prefix` (needed by models such as E5 and BGE). |
| `fake` | `fake.py` | Hashed bag-of-words vectors. Deterministic, offline, and good enough for keyword-like retrieval in tests. |

`--offline` replaces every `embedder` component with `fake`.

Changing the embedding model invalidates existing vectors. Re-ingest into a new index path after the change.

New adapters need a subclass of `EmbedderContract` in `tests/contract/test_embedder_contract.py`.
