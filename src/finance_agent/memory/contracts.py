"""通用 memory 契约。

Memory 的作用域用 namespace 表达，而不是把每一种作用域都扩展成一个字段。
约定格式为 ``<scope>:<id>``，例如 ``session:abc`` 或 ``workspace:finance``。
"""
from __future__ import annotations

from enum import Enum


class MemoryKind(str, Enum):
    """允许进入普通 LLM 上下文的两类记忆。"""

    QUERY_HISTORY = "query_history"
    SEMANTIC = "semantic"


def make_namespace(scope: str, scope_id: str) -> str:
    """构造稳定的 memory namespace。"""
    normalized_scope = str(scope).strip().lower()
    normalized_id = str(scope_id).strip()
    if not normalized_scope or not normalized_id:
        raise ValueError("memory namespace requires both scope and id")
    return f"{normalized_scope}:{normalized_id}"
