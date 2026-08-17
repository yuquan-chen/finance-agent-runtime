from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class PublicMemoryEntry(BaseModel):
    memory_id: str
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
    # 新增：SQL 和查询结果摘要
    sql_template: str | None = None
    # 已脱敏的业务目标，供重新生成查询路径重新生成 SQL；不保存真实结果值。
    goal: str | None = None
    user_query: str | None = None
    result_summary: str | None = None  # 查询结果的文字摘要
    created_at: str = Field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))


class PublicMemoryStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, entry: PublicMemoryEntry) -> PublicMemoryEntry:
        with self.path.open("a", encoding="utf-8") as file:
            file.write(entry.model_dump_json() + "\n")
        return entry

    def latest(self, limit: int = 5, session_id: str | None = None) -> list[PublicMemoryEntry]:
        if not self.path.exists():
            return []
        lines = [line for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
        records = [PublicMemoryEntry.model_validate(json.loads(line)) for line in lines]
        if session_id is not None:
            records = [record for record in records if record.session_id == session_id]
        records = records[-limit:]
        return list(reversed(records))

    def context_for_llm(self, session_id: str, limit: int = 5) -> list[dict[str, Any]]:
        """返回 memory 条目，用于注入到 LLM 上下文。"""
        entries = []
        for candidate, entry in enumerate(self.latest(limit, session_id=session_id), start=1):
            entries.append({
                "type": "memory",
                # 编号只在本次上下文中有效，按最新到最旧排列；LLM 不生成内部 result_ref。
                "query_candidate": candidate,
                "name": entry.method_name,
                "description": f"之前的查询候选 {candidate}",
                # 参数化 SQL 可以作为重新生成查询路径的参考；真实参数和结果值不进入 LLM。
                "content": f"SQL 模板: {entry.sql_template or '无'}\n结果结构摘要: {entry.result_summary or '无'}",
                "goal": entry.goal or "",
                "sql_template": entry.sql_template or "",
                "plan_result_ref": entry.plan_result_ref,
                "fields": entry.fields,
                "row_count": entry.row_count,
                "result_shape": entry.result_shape,
            })
        return entries

    def delete_session(self, session_id: str) -> int:
        """永久移除一个会话的公开安全摘要。"""
        if not self.path.exists():
            return 0
        records = [PublicMemoryEntry.model_validate(json.loads(line)) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
        retained = [record for record in records if record.session_id != session_id]
        self.path.write_text("".join(record.model_dump_json() + "\n" for record in retained), encoding="utf-8")
        return len(records) - len(retained)
