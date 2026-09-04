"""Query-history naming aliases for the canonical safe MemoryStore."""
from finance_agent.memory.memory_store import MemoryRecord, MemoryStore

QueryCard = MemoryRecord
QueryCardStore = MemoryStore

__all__ = ["QueryCard", "QueryCardStore"]
