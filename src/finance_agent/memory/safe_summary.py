from __future__ import annotations

import re
from typing import Any

from finance_agent.harness.analysis_schema import ExecutionResultCard, MethodDraft
from finance_agent.memory.private_result_store import PrivateResultRecord
from finance_agent.memory.public_memory import PublicMemoryEntry


def build_public_memory_entry(
    *,
    request_id: str,
    session_id: str,
    method: MethodDraft,
    execution_card: ExecutionResultCard,
    private_record: PrivateResultRecord,
    user_query: str | None = None,
    plan_result_ref: str | None = None,
) -> PublicMemoryEntry:
    # 构建查询结果摘要
    result_summary = _build_result_summary(execution_card.result, execution_card.row_count)

    return PublicMemoryEntry(
        memory_id=f"memory_{private_record.result_ref}",
        request_id=request_id,
        session_id=session_id,
        result_ref=private_record.result_ref,
        plan_result_ref=plan_result_ref,
        method_name=method.name,
        method_type=method.method_type,
        fields=execution_card.data_authorization.fields,
        result_shape=infer_result_shape(execution_card.result),
        row_count=execution_card.row_count,
        real_database_used=execution_card.real_database_used,
        values_visible_to_llm=False,
        sql_template=method.sql_template,
        goal=_redact_goal(method.goal, method.params),
        user_query=user_query,
        result_summary=result_summary,
    )


def _build_result_summary(result: dict[str, Any] | list[dict[str, Any]], row_count: int) -> str:
    """构建查询结果的文字摘要。"""
    if isinstance(result, list):
        if not result:
            return "查询结果为空"
        columns = list(result[0].keys()) if result else []
        return f"返回 {row_count} 行，字段: {', '.join(columns[:5])}"
    elif isinstance(result, dict):
        keys = list(result.keys())
        return f"返回对象，字段: {', '.join(keys[:5])}"
    return "查询完成"


def _redact_goal(goal: str, params: dict[str, Any] | None) -> str:
    """Keep user values in the private method, but remove them from safe memory."""
    redacted = goal or ""
    for value in sorted((str(value) for value in (params or {}).values() if value is not None), key=len, reverse=True):
        if value.strip():
            redacted = re.sub(re.escape(value), "[参数]", redacted, flags=re.IGNORECASE)
    return redacted


def infer_result_shape(result: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
    if isinstance(result, list):
        columns: list[str] = []
        seen = set()
        for row in result:
            for key in row:
                if key not in seen:
                    seen.add(key)
                    columns.append(key)
        return {
            "kind": "rows",
            "columns": columns,
            "row_count_hidden": True,
            "values_hidden": True,
        }
    return {
        "kind": "object",
        "keys": list(result.keys()),
        "values_hidden": True,
    }
