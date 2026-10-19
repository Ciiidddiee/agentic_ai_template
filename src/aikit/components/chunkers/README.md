# components/chunkers

They split documents into chunks. Each implements `Chunker`: `split(document) -> list[Chunk]`.

| Type | File | Notes |
|---|---|---|
| `recursive` | `recursive.py` | Splits on paragraphs, then lines, then sentences, then words, respecting `chunk_size` / `chunk_overlap` (in characters) |
| `markdown` | `markdown.py` | Splits by heading first, then recursively. Stores the heading path in `metadata.section`, which is used in citations. |

`_split.py` provides `split_text` and `make_chunk`. Chunk ids are `sha256(source + text)`, so re-ingesting unchanged content is a no-op and changed content replaces the stale chunks.

New chunkers must pass `tests/contract/test_chunker_contract.py`.
