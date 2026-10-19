"""aikit: a config-driven kernel for RAG and agentic AI applications."""

from aikit.core.context import RunContext
from aikit.core.registry import register, registry
from aikit.core.tooling import BaseTool, tool
from aikit.core.types import Message, RunEvent, RunResult

__version__ = "0.1.0"

__all__ = [
    "BaseTool",
    "Message",
    "RunContext",
    "RunEvent",
    "RunResult",
    "__version__",
    "register",
    "registry",
    "tool",
]
