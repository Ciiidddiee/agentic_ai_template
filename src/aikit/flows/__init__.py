"""Flows combine components. Importing this package registers the built-in flows."""

from aikit.flows.agent import AgentFlow
from aikit.flows.base import BaseFlow, collect_result
from aikit.flows.ingest import IngestFlow
from aikit.flows.rag import RagFlow

__all__ = ["AgentFlow", "BaseFlow", "IngestFlow", "RagFlow", "collect_result"]
