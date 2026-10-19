# tests/contract

Behaviour every implementation of an interface must have. A new adapter is supported once a subclass of its suite passes.

| File | Suite | Implementations tested |
|---|---|---|
| `test_llm_contract.py` | `LLMContract` | `FakeLLM`, `OpenAICompatLLM` (plus retry and auth tests) |
| `test_embedder_contract.py` | `EmbedderContract` | `FakeEmbedder`, `OpenAICompatEmbedder` (plus batching and prefixes) |
| `test_vector_store_contract.py` | `VectorStoreContract` | `InMemoryVectorStore`: upsert idempotency, filters, ACLs, delete, persistence |
| `test_chunker_contract.py` | `TestChunkerContract` (parametrised) | `recursive`, `markdown` |

`gateway.py` contains `MockGateway`, an in-process OpenAI-compatible server built on `httpx.MockTransport`. It can fail the first N requests with a given status code.

## Adding an adapter

```python
class TestPgVectorStore(VectorStoreContract):
    @pytest.fixture
    def store(self, tmp_path):
        return PgVectorStore(dsn=os.environ["TEST_PG_DSN"])
```

Mark suites that need real infrastructure (`@pytest.mark.skipif(not os.getenv(...))`) so the default run stays offline.
