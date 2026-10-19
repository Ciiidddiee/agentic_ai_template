# project/prompts

Prompts are code: version them here, review them in pull requests, and check every change with `aikit eval`.

| File | Used by | Notes |
|---|---|---|
| `answer_with_citations.md` | `rag` flow (`prompt:`) | System prompt: answer only from the numbered passages and cite them as `[n]` |
| `agent_system.md` | `agent` flow (`prompt:`) | System prompt: when to search, when to use tools, and that refunds need approval |

Config fields such as `prompt:` and `user_template:` accept a file path or inline text. The RAG `user_template` supports the `{context}` and `{question}` placeholders (default `Context:\n{context}\n\nQuestion: {question}`).

Keep business rules out of prompts. Anything that must always hold belongs in `project/domain/`, where tools enforce it.
