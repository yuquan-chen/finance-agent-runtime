"""Direct DB 执行器工厂。"""
from __future__ import annotations

from finance_agent.executor.readonly_db import ReadonlyDbExecutor
from finance_agent.executor.executor_registry import register_executor


@register_executor("direct_db")
def create_direct_db(settings, policy):
    if not settings.database_url:
        raise RuntimeError("direct_db mode requires DATABASE_URL, but MVP should prefer EXECUTOR_MODE=mock")
    return ReadonlyDbExecutor(settings.database_url, policy)
