"""Allowlisted PostgreSQL executor for local integration testing."""
from __future__ import annotations

from typing import Any

from finance_agent.executor.executor_registry import register_executor
from finance_agent.executor.readonly_db import ReadonlyDbExecutor
from finance_agent.harness.analysis_schema import MethodDraft, MockDryRunResult
from finance_agent.metadata.policy import Policy
from finance_agent.query.safe_requests import SafeQueryRegistry, SafeQueryRequest


class SafeDbExecutor:
    """Execute only query IDs from the versioned safe-query registry.

    This executor deliberately does not fall back to ``method.sql_template``.
    A method without an explicit allowlisted query ID is refused.
    """

    def __init__(self, database_url: str, policy: Policy, registry: SafeQueryRegistry):
        self.database = ReadonlyDbExecutor(database_url, policy)
        self.registry = registry
        self.policy = policy

    def execute_safe_request(self, request: SafeQueryRequest, registry: SafeQueryRegistry | None = None):
        return self.database.execute_safe_request(request, registry or self.registry)

    def execute_method(
        self,
        method: MethodDraft,
        *,
        extra_tables: dict[str, list[dict[str, Any]]] | None = None,
    ) -> MockDryRunResult:
        if extra_tables:
            return self._failed("safe_db does not execute dependent temporary tables")
        if method.method_type != "sql":
            return self._failed("safe_db only supports allowlisted SQL query IDs")
        if not method.query_id:
            return self._failed("safe_db requires MethodDraft.query_id; raw SQL is not an execution contract")
        try:
            request = SafeQueryRequest(
                query_id=method.query_id,
                params=method.params,
                page=1,
                page_size=min(self.policy.max_rows, 20),
            )
            result = self.execute_safe_request(request)
        except Exception as exc:  # noqa: BLE001 - normalize all backend failures for the query contract
            return self._failed(f"{type(exc).__name__}: {exc}")
        return MockDryRunResult(
            status="passed",
            output=result.rows,
            input_summary={
                "runner": "safe_query_registry",
                "execution_mode": "safe_db",
                "real_database_used": True,
                "query_id": method.query_id,
                "row_count": result.row_count,
                "elapsed_ms": result.elapsed_ms,
            },
        )

    @staticmethod
    def _failed(error: str) -> MockDryRunResult:
        return MockDryRunResult(
            status="failed",
            errors=[error],
            input_summary={
                "runner": "safe_query_registry",
                "execution_mode": "safe_db",
                "real_database_used": False,
            },
        )


@register_executor("safe_db")
def create_safe_db(settings, policy):
    if not settings.database_url:
        raise RuntimeError("safe_db mode requires DATABASE_URL")
    registry = SafeQueryRegistry.from_yaml(settings.safe_query_definitions_path)
    return SafeDbExecutor(settings.database_url, policy, registry)
