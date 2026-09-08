"""统一 MethodDraft 执行入口。

Runtime 只依赖这个适配层，不需要知道具体执行器是 mock 还是数据库实现。
"""
from __future__ import annotations

from typing import Any

from finance_agent.harness.analysis_schema import MethodDraft, MockDryRunResult


def execute_method(
    executor: Any,
    method: MethodDraft,
    *,
    extra_tables: dict[str, list[dict[str, Any]]] | None = None,
) -> MockDryRunResult:
    """Execute a method through the registered executor contract."""
    method_executor = getattr(executor, "execute_method", None)
    if not callable(method_executor):
        raise TypeError(
            f"executor {type(executor).__name__} does not implement the required execute_method contract"
        )
    result = method_executor(method, extra_tables=extra_tables)
    if not isinstance(result, MockDryRunResult):
        raise TypeError(
            f"executor {type(executor).__name__}.execute_method must return MockDryRunResult"
        )
    return result
