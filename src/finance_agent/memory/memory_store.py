"""Single store for all safe, model-retrievable memory.

The store deliberately holds only two kinds of records: ``query_history`` for
session follow-up queries and ``semantic`` for stable preferences, feedback,
and project context. Private results, run state, and audit events belong to
their own stores and never pass through this module.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from finance_agent.memory.contracts import MemoryKind, make_namespace
from finance_agent.memory.taxonomy import MemoryType


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class MemoryRecord(BaseModel):
    """One safe memory record persisted by :class:`MemoryStore`."""

    id: str = Field(default_factory=lambda: f"memory_{uuid.uuid4().hex}")
    namespace: str
    kind: MemoryKind
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)

    @property
    def name(self) -> str:
        return str(self.metadata.get("name") or self.id)

    @property
    def description(self) -> str:
        return str(self.metadata.get("description") or "")

    @property
    def type(self) -> MemoryType:
        try:
            return MemoryType(str(self.metadata.get("type") or MemoryType.PROJECT.value))
        except ValueError:
            return MemoryType.PROJECT


@dataclass
class MemoryFile:
    """Compatibility input/output for the former Markdown semantic-memory API."""

    name: str
    description: str
    type: MemoryType
    content: str
    path: Path
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    session_id: str = ""
    namespace: str = ""


class MemoryStore:
    """Canonical JSONL store for safe query history and semantic memory."""

    def __init__(self, path: Path):
        # Earlier callers passed a directory for Markdown files. Keep that
        # constructor working while putting new records in one JSONL file.
        self.path = path if path.suffix else path / "memories.jsonl"
        self.base_path = self.path.parent
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path = self.path
        self._migrate_legacy_markdown()

    def _migrate_legacy_markdown(self) -> None:
        """Move old semantic Markdown records into JSONL and remove duplicates.

        The old directory used the same stem as the JSONL file, for example
        ``public_memory.jsonl`` and ``public_memory/*.md``. Query-history
        Markdown files duplicated the JSONL query cards, so they are removed
        rather than imported. Other valid records become ``semantic`` rows.
        """
        legacy_dir = self.path.parent / self.path.stem
        if not legacy_dir.is_dir():
            return
        legacy_files = list(legacy_dir.glob("*.md"))
        if not legacy_files:
            return

        records = self._read_all()
        known_ids = {record.id for record in records}
        for legacy_path in legacy_files:
            if legacy_path.name == "MEMORY.md" or legacy_path.stem.startswith("query_history_"):
                continue
            memory = self._parse_legacy_semantic_file(legacy_path)
            if memory is None:
                continue
            record_id = f"legacy_semantic_{legacy_path.stem}"
            if record_id in known_ids:
                continue
            records.append(
                MemoryRecord(
                    id=record_id,
                    namespace=memory.namespace,
                    kind=MemoryKind.SEMANTIC,
                    content=memory.content,
                    metadata={
                        "name": memory.name,
                        "description": memory.description,
                        "type": memory.type.value,
                    },
                    created_at=memory.created_at or _now(),
                    updated_at=memory.updated_at or memory.created_at or _now(),
                )
            )
            known_ids.add(record_id)

        # Writing canonical records also upgrades legacy query-card JSON rows.
        self._write_all(records)
        for legacy_path in legacy_files:
            legacy_path.unlink()
        try:
            legacy_dir.rmdir()
        except OSError:
            # Leave unrelated files alone; no runtime code reads this directory.
            pass

    @staticmethod
    def _parse_legacy_semantic_file(path: Path) -> MemoryFile | None:
        text = path.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
        if not match:
            return None
        frontmatter = {}
        for line in match.group(1).splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                frontmatter[key.strip()] = value.strip()
        try:
            memory_type = MemoryType(frontmatter.get("type", MemoryType.PROJECT.value))
        except ValueError:
            memory_type = MemoryType.PROJECT
        session_id = frontmatter.get("session_id", "")
        namespace = frontmatter.get("namespace") or (
            make_namespace("session", session_id) if session_id else make_namespace("global", "default")
        )
        return MemoryFile(
            name=frontmatter.get("name", path.stem),
            description=frontmatter.get("description", ""),
            type=memory_type,
            content=match.group(2).strip(),
            path=path,
            created_at=frontmatter.get("created_at", ""),
            updated_at=frontmatter.get("updated_at", ""),
            session_id=session_id,
            namespace=namespace,
        )

    def _read_all(self) -> list[MemoryRecord]:
        if not self.path.exists():
            return []
        records: list[MemoryRecord] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                records.append(MemoryRecord.model_validate_json(line))
            except Exception:
                legacy = self._from_legacy_query_card(line)
                if legacy:
                    records.append(legacy)
        return records

    @staticmethod
    def _from_legacy_query_card(line: str) -> MemoryRecord | None:
        """Read old public_memory.jsonl rows until the next write migrates them."""
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not {"memory_id", "method_name", "session_id"}.issubset(data):
            return None
        return MemoryRecord(
            id=str(data["memory_id"]),
            namespace=make_namespace("session", str(data["session_id"])),
            kind=MemoryKind.QUERY_HISTORY,
            content=(
                f"SQL 模板: {data.get('sql_template') or '无'}\n"
                f"结果结构摘要: {data.get('result_summary') or '无'}"
            ),
            metadata={
                "name": data.get("method_name", "query"),
                "description": "之前的查询候选",
                "request_id": data.get("request_id", ""),
                "result_ref": data.get("result_ref", ""),
                "plan_result_ref": data.get("plan_result_ref"),
                "method_type": data.get("method_type", ""),
                "fields": data.get("fields", []),
                "result_shape": data.get("result_shape", {}),
                "row_count": data.get("row_count", 0),
                "real_database_used": data.get("real_database_used", False),
                "sql_template": data.get("sql_template") or "",
                "goal": data.get("goal") or "",
                "user_query": data.get("user_query") or "",
                "result_summary": data.get("result_summary") or "",
            },
            created_at=data.get("created_at") or _now(),
            updated_at=data.get("created_at") or _now(),
        )

    def _write_all(self, records: list[MemoryRecord]) -> None:
        self.path.write_text(
            "".join(record.model_dump_json() + "\n" for record in records),
            encoding="utf-8",
        )

    @staticmethod
    def _session_namespace(session_id: str) -> str:
        return make_namespace("session", session_id)

    def upsert(self, record: MemoryRecord) -> MemoryRecord:
        records = self._read_all()
        record.updated_at = _now()
        for index, current in enumerate(records):
            if current.id == record.id:
                record.created_at = current.created_at
                records[index] = record
                break
        else:
            records.append(record)
        self._write_all(records)
        return record

    def append_query_history(
        self,
        *,
        memory_id: str,
        session_id: str,
        content: str,
        metadata: dict[str, Any],
        created_at: str | None = None,
    ) -> MemoryRecord:
        return self.upsert(
            MemoryRecord(
                id=memory_id,
                namespace=self._session_namespace(session_id),
                kind=MemoryKind.QUERY_HISTORY,
                content=content,
                metadata=metadata,
                created_at=created_at or _now(),
                updated_at=created_at or _now(),
            )
        )

    def query_history(self, session_id: str, limit: int = 5) -> list[MemoryRecord]:
        records = [
            (index, record)
            for index, record in enumerate(self._read_all())
            if record.kind is MemoryKind.QUERY_HISTORY
            and record.namespace == self._session_namespace(session_id)
        ]
        records.sort(key=lambda item: (item[1].updated_at, item[0]), reverse=True)
        return [record for _, record in records[:limit]]

    def context_for_llm(self, session_id: str, limit: int = 5) -> list[dict[str, Any]]:
        """Safe query-history projection. Backend references stay private."""
        # One execution can produce several method records. Collapse those
        # records into one logical query context before exposing history.
        grouped: dict[str, list[MemoryRecord]] = {}
        for record in self.query_history(session_id, max(limit * 10, 50)):
            query_id = str(record.metadata.get("query_id") or record.id)
            grouped.setdefault(query_id, []).append(record)

        contexts: list[dict[str, Any]] = []
        for candidate, (query_id, records) in enumerate(list(grouped.items())[:limit], start=1):
            record = records[0]
            contexts.append(
                {
                    "type": "memory",
                    "query_candidate": candidate,
                    "query_id": query_id,
                    "name": record.name,
                    "description": f"之前的查询候选 {candidate}",
                    "content": record.content,
                    "goal": str(record.metadata.get("goal") or ""),
                    "sql_template": str(record.metadata.get("sql_template") or ""),
                    "fields": list(record.metadata.get("fields") or []),
                    "row_count": int(record.metadata.get("row_count") or 0),
                    "result_shape": dict(record.metadata.get("result_shape") or {}),
                    "method_count": len(records),
                    "methods": [
                        {
                            "name": item.name,
                            "goal": str(item.metadata.get("goal") or ""),
                            "fields": list(item.metadata.get("fields") or []),
                        }
                        for item in records
                    ],
                }
            )
        return contexts

    def list_semantic_memories(self, namespace: str) -> list[MemoryRecord]:
        return [
            record
            for record in self._read_all()
            if record.kind is MemoryKind.SEMANTIC and record.namespace == namespace
        ]

    def get_semantic_memory(self, name: str, namespace: str | None = None) -> MemoryRecord | None:
        for record in self._read_all():
            if record.kind is not MemoryKind.SEMANTIC or record.name != name:
                continue
            if namespace is None or record.namespace == namespace:
                return record
        return None

    def semantic_manifest(self, namespace: str, limit: int = 50) -> str:
        records = self.list_semantic_memories(namespace)
        records.sort(key=lambda record: record.updated_at, reverse=True)
        lines = ["可用的语义记忆：\n"]
        for record in records[:limit]:
            lines.append(f"- [{record.type.value}] {record.name}: {record.description}")
        return "\n".join(lines)

    def save_semantic(
        self,
        *,
        name: str,
        description: str,
        memory_type: MemoryType,
        content: str,
        namespace: str,
        memory_id: str | None = None,
    ) -> MemoryRecord:
        existing = self.get_semantic_memory(name, namespace)
        return self.upsert(
            MemoryRecord(
                id=memory_id or (existing.id if existing else f"semantic_{uuid.uuid4().hex}"),
                namespace=namespace,
                kind=MemoryKind.SEMANTIC,
                content=content,
                metadata={"name": name, "description": description, "type": memory_type.value},
            )
        )

    # Compatibility API for the old semantic-memory implementation.
    def save_memory(self, memory: MemoryFile) -> MemoryFile:
        namespace = memory.namespace or self._session_namespace(memory.session_id)
        record = self.save_semantic(
            name=memory.name,
            description=memory.description,
            memory_type=memory.type,
            content=memory.content,
            namespace=namespace,
        )
        return self._as_memory_file(record)

    def list_memories(self) -> list[MemoryFile]:
        return [self._as_memory_file(record) for record in self._read_all() if record.kind is MemoryKind.SEMANTIC]

    def get_memory(self, name: str) -> MemoryFile | None:
        record = self.get_semantic_memory(name)
        return self._as_memory_file(record) if record else None

    def list_session_memories(self, session_id: str) -> list[MemoryFile]:
        return [self._as_memory_file(record) for record in self.list_semantic_memories(self._session_namespace(session_id))]

    def list_namespace_memories(self, namespace: str) -> list[MemoryFile]:
        return [self._as_memory_file(record) for record in self.list_semantic_memories(namespace)]

    def get_manifest(self, limit: int = 50, session_id: str | None = None) -> str:
        if session_id is None:
            return self.semantic_manifest("global:default", limit)
        return self.semantic_manifest(self._session_namespace(session_id), limit)

    def save_query_history(
        self,
        user_query: str,
        result_summary: str,
        tables: list[str] | None = None,
        fields: list[str] | None = None,
        session_id: str = "",
    ) -> MemoryRecord:
        """Compatibility helper; runtime no longer calls this duplicate path."""
        return self.append_query_history(
            memory_id=f"query_{uuid.uuid4().hex}",
            session_id=session_id,
            content=f"SQL 模板: 无\n结果结构摘要: {result_summary}",
            metadata={
                "name": "query_history",
                "description": f"查询: {user_query[:50]}",
                "user_query": user_query,
                "result_summary": result_summary,
                "tables": tables or [],
                "fields": fields or [],
            },
        )

    def get_recent_queries(self, limit: int = 3, session_id: str | None = None) -> list[dict[str, Any]]:
        if not session_id:
            return []
        return [
            {
                "user_query": str(record.metadata.get("user_query") or ""),
                "tables": ", ".join(record.metadata.get("tables") or []),
                "fields": ", ".join(record.metadata.get("fields") or []),
                "result_summary": str(record.metadata.get("result_summary") or ""),
            }
            for record in self.query_history(session_id, limit)
        ]

    def delete_session(self, session_id: str, kind: MemoryKind | None = None) -> int:
        namespace = self._session_namespace(session_id)
        records = self._read_all()
        retained = [
            record
            for record in records
            if not (record.namespace == namespace and (kind is None or record.kind is kind))
        ]
        self._write_all(retained)
        return len(records) - len(retained)

    def delete_session_memories(self, session_id: str) -> int:
        return self.delete_session(session_id, MemoryKind.SEMANTIC)

    def clear_all(self) -> int:
        records = self._read_all()
        self._write_all([])
        return len(records)

    def _as_memory_file(self, record: MemoryRecord) -> MemoryFile:
        session_id = record.namespace.partition(":")[2] if record.namespace.startswith("session:") else ""
        return MemoryFile(
            name=record.name,
            description=record.description,
            type=record.type,
            content=record.content,
            path=self.path,
            created_at=record.created_at,
            updated_at=record.updated_at,
            session_id=session_id,
            namespace=record.namespace,
        )
