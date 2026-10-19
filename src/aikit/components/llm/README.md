# components/llm

Chat models. They implement `LLM` from `core/ports.py`: `chat(messages, tools=None, **options) -> LLMResponse` and `stream(messages, **options) -> AsyncIterator[str]`.

| Type | File | Use |
|---|---|---|
| `openai_compat` | `openai_compat.py` | Any `/v1/chat/completions` gateway (the internal LLM, vLLM, Azure, ...). Supports tool calls, streaming, retries, custom `headers`, `extra_body`, and `verify` for internal CAs. |
| `fake` | `fake.py` | Deterministic offline model. Without `responses` it answers heuristically: it quotes passage `[n]`, picks tools by word overlap, and returns `{}` for JSON prompts. With `responses` it replays a script (strings or `{"tool_calls": [...]}`). |

`--offline` replaces every `llm` component with `fake` automatically.

To add a model API, implement `chat` and `stream`, optionally `aclose`, and add a subclass of `LLMContract` in `tests/contract/test_llm_contract.py`.
