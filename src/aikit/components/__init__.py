"""Built-in adapters. Importing this package registers all of them.

Optional third-party dependencies (pypdf, python-docx, ...) are imported lazily
inside the component that needs them, so importing this package never fails.
"""

from aikit.components import (
    chunkers,
    embeddings,
    guardrails,
    llm,
    loaders,
    memory,
    rerankers,
    retrievers,
    tools,
    vectorstores,
)

__all__ = [
    "chunkers",
    "embeddings",
    "guardrails",
    "llm",
    "loaders",
    "memory",
    "rerankers",
    "retrievers",
    "tools",
    "vectorstores",
]
