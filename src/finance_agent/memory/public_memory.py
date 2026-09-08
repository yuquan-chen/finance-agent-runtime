"""Compatibility facade for query-history records.

New code should use :class:`finance_agent.memory.memory_store.MemoryStore`.
This module remains so existing callers of ``PublicMemoryStore`` keep working;
it no longer owns a second file or a second persistence model.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from finance_agent.memory.contracts import MemoryKind
from finance_agent.memory.memory_store import MemoryRecord, MemoryStore


class PublicMemoryEntry(BaseModel):
    """Legacy query-card shape, mapped into the canonical memory record."""

    memory_id: str
    # Stable, model-visible handle for a logical query run. This is not a
    # private result_ref and remains stable when method ordering changes.
    query_id: str | None = None
    request_id: str
    session_id: str = ""
    result_ref: str
    plan_result_ref: str | None = None
    method_name: str
    method_type: str
    fields: list[str]
    result_shape: dict[str, Any]
    row_count: int
    real_database_used: bool
    values_visible_to_llm: bool = False
    sql_template: str | None = None
    goal: str | None = None
    user_query: str | None = None
    result_summary: str | None = None
    created_at: str = Field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def to_memory_parts(self) -> tuple[str, dict[str, Any]]:
        return (
            f"SQL 模板: {self.sql_template or '无'}\n结果结构摘要: {self.result_summary or '无'}",
            {
                "name": self.method_name,
                "description": "之前的查询候选",
                "request_id": self.request_id,
                "query_id": self.query_id,
                "result_ref": self.result_ref,
                "plan_result_ref": self.plan_result_ref,
                "method_type": self.method_type,
                "fields": self.fields,
                "result_shape": self.result_shape,
                "row_count": self.row_count,
                "real_database_used": self.real_database_used,
                "values_visible_to_llm": self.values_visible_to_llm,
                "sql_template": self.sql_template or "",
                "goal": self.goal or "",
                "user_query": self.user_query or "",
                "result_summary": self.result_summary or "",
            },
        )

    @classmethod
    def from_record(cls, record: MemoryRecord) -> PublicMemoryEntry:
        metadata = record.metadata
        return cls(
            memory_id=record.id,
            request_id=str(metadata.get("request_id") or ""),
            query_id=str(metadata.get("query_id") or "") or None,
            session_id=record.namespace.partition(":")[2] if record.namespace.startswith("session:") else "",
            result_ref=str(metadata.get("result_ref") or ""),
            plan_result_ref=metadata.get("plan_result_ref"),
            method_name=record.name,
            method_type=str(metadata.get("method_type") or ""),
            fields=list(metadata.get("fields") or []),
            result_shape=dict(metadata.get("result_shape") or {}),
            row_count=int(metadata.get("row_count") or 0),
            real_database_used=bool(metadata.get("real_database_used")),
            values_visible_to_llm=bool(metadata.get("values_visible_to_llm")),
            sql_template=str(metadata.get("sql_template") or "") or None,
            goal=str(metadata.get("goal") or "") or None,
            user_query=str(metadata.get("user_query") or "") or None,
            result_summary=str(metadata.get("result_summary") or "") or None,
            created_at=record.created_at,
        )


class PublicMemoryStore:
    """Legacy facade backed by the single canonical ``MemoryStore``."""

    def __init__(self, path: Path | MemoryStore):
        self.store = path if isinstance(path, MemoryStore) else MemoryStore(path)
        self.path = self.store.path

    def append(self, entry: PublicMemoryEntry) -> PublicMemoryEntry:
        content, metadata = entry.to_memory_parts()
        self.store.append_query_history(
            memory_id=entry.memory_id,
            session_id=entry.session_id,
            content=content,
            metadata=metadata,
            created_at=entry.created_at,
        )
        return entry

    def latest(self, limit: int = 5, session_id: str | None = None) -> list[PublicMemoryEntry]:
        if session_id is None:
            records = [record for record in self.store._read_all() if record.kind is MemoryKind.QUERY_HISTORY]
            records.sort(key=lambda record: record.updated_at, reverse=True)
            return [PublicMemoryEntry.from_record(record) for record in records[:limit]]
        return [PublicMemoryEntry.from_record(record) for record in self.store.query_history(session_id, limit)]

    def context_for_llm(self, session_id: str, limit: int = 5) -> list[dict[str, Any]]:
        return self.store.context_for_llm(session_id, limit)

    def delete_session(self, session_id: str) -> int:
        return self.store.delete_session(session_id, MemoryKind.QUERY_HISTORY)
