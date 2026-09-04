"""Semantic-memory naming aliases for the canonical safe MemoryStore."""
from finance_agent.memory.memory_store import MemoryRecord, MemoryStore

SemanticMemory = MemoryRecord
SemanticMemoryStore = MemoryStore

__all__ = ["SemanticMemory", "SemanticMemoryStore"]
