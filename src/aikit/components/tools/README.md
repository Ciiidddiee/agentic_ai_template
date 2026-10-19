# components/tools

Generic, reusable agent tools. App-specific tools belong in [`project/tools/`](../../../../project/tools/README.md).

| Type | File | Capabilities | Notes |
|---|---|---|---|
| `retriever_tool` | `retriever_tool.py` | `read` | Exposes a retriever to the agent (agentic RAG). Returns numbered passages, and citations in `ToolResult.data`. Set `name` / `description` per use. |
| `http` | `http.py` | GET: `read`, `network`; other methods: `write`, `network` | Calls an internal REST endpoint. Path parameters are URL-quoted, and output is truncated to `max_chars`. |

All tools subclass `core.tooling.BaseTool`, or are built with `@tool`. Declare honest capabilities: the policy uses them to decide what needs human approval.
