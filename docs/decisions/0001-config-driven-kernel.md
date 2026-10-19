# 0001: Config-driven kernel shared by RAG and agent apps

- Status: accepted
- Date: 2026-10-18

## Context

The organisation will build many RAG and agent applications on one internal LLM gateway. Copy-pasting a project per app leads to drift: every fork fixes retries, ACLs, and evals differently. Frameworks such as LangChain or LlamaIndex move quickly and make it hard to enforce one security and observability standard.

## Decision

Build a small kernel (`aikit`) in which:

- RAG and agents share the same components. Retrieval is a component that a RAG flow calls directly and an agent calls through `retriever_tool`.
- Each app is defined by a YAML config (`project/app.yaml`) that names components by registry type and wires them with `"@name"` references.
- Constructor signatures are the config schema. The builder validates parameters with pydantic models generated from them, so a misconfiguration fails at startup with its config path.
- App-specific code lives only in `project/`.

## Consequences

- Switching between plain RAG, an agent, and agentic RAG, or swapping a model, store, or reranker, is a config change, and evals can compare the results.
- Teams need to learn the registry and config conventions. `aikit components --schema` and the docs reduce that cost.
- Frameworks can still be used inside a component (for example, a LlamaIndex-based loader) without leaking into flows.
