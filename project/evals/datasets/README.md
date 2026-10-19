# project/evals/datasets

One JSON object per line. Every case needs an `id`.

## rag_golden.jsonl (RAG cases)

```json
{"id": "return-window", "question": "How many days do I have to return an item?",
 "expected_sources": ["refund_policy.md"], "must_include": ["30 days"], "k": 4}
```

| Field | Meaning |
|---|---|
| `question` | Input to the flow |
| `expected_sources` | Source file names that must be retrieved (recall@k) and cited |
| `must_include` | Phrases the answer must contain (case-insensitive) |
| `k` | Cut-off for recall@k |
| `groups` | Caller groups for the run (ACL testing) |
| `forbidden_sources` | Sources that must not be retrieved; fails with `acl_leak` |
| `min_recall` | Required recall (default 1.0) |

## agent_tasks.jsonl (agent cases)

| Field | Meaning |
|---|---|
| `input` | Task for the agent |
| `expected_tools` / `forbidden_tools` | Tools that must or must not be called |
| `must_include` | Phrases the final answer must contain |
| `expected_status` | For example `completed` or `awaiting_approval` |

The kind is detected from the fields (`question` → RAG, `input` → agent) or set with `kind:` in the config.
