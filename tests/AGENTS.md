# AGENTS.md: tests/

Applies to everything under `tests/`. Also follow the root [AGENTS.md](../AGENTS.md).

- Everything runs offline. Never call the real gateway; use `FakeLLM`, `FakeEmbedder`, or `tests/contract/gateway.py:MockGateway`.
- Async tests need no decorator (`asyncio_mode = auto`).
- Choose the layer:
  - `unit/` for pure logic;
  - `contract/` for adapters (subclass the suite);
  - `integration/` for full profiles via `offline_runtime`.
- Prefer scripted fakes when the assertion depends on model output:

```python
from aikit.components.llm.fake import FakeLLM

llm = FakeLLM(
    responses=[
        {"tool_calls": [{"name": "lookup", "arguments": {"q": "x"}}]},
        "final answer",
    ]
)
```

- Integration tests: `runtime = offline_runtime("project/profiles/rag.yaml", **{"flow.top_k": 2})`. The fixture uses a temporary index and closes the runtime.
- Register throwaway components on a fresh registry (`reg = Registry(); reg.add("llm", "dummy", DummyLLM)`) and pass it as `Builder(specs, target=reg)`, never on the global registry.
- Assert on `RunResult.status`, events, and citations, not on exact fake wording.
- When you add a test file, add a row to the folder's `README.md`.
