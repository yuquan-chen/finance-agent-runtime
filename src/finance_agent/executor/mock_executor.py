from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from finance_agent.builder.sql_builder import assert_readonly_sql
from finance_agent.harness.plan_schema import Intent, QueryPlan
from finance_agent.harness.analysis_schema import MethodDraft, MockDryRunResult
from finance_agent.metadata.policy import Policy
from finance_agent.sandbox.mock_data import load_catalog_mock_data
from finance_agent.sandbox.mock_sandbox import run_simulated_real_execution


@dataclass(frozen=True)
class QueryResult:
    rows: list[dict[str, Any]]
    row_count: int
    elapsed_ms: int


# 应用 mock 查询只使用测试环境快照，不混入合成 Company 或交易记录。
_MOCK_DATA: dict[str, list[dict[str, Any]]] = load_catalog_mock_data()


class MockExecutor:
    """Static local executor for feasibility tests.

    It intentionally does not connect to any database. It validates the SQL is
    read-only, then computes deterministic fixture-backed results from the
    validated QueryPlan.
    """

    def __init__(self, policy: Policy):
        self.policy = policy

    def execute(self, sql: str, plan: QueryPlan | None = None) -> QueryResult:
        assert_readonly_sql(sql, self.policy)
        if plan is None:
            raise RuntimeError("MockExecutor requires a validated plan")
        started = time.time()
        rows = self._execute_plan(plan)
        rows = rows[: self.policy.max_rows]
        return QueryResult(rows=rows, row_count=len(rows), elapsed_ms=int((time.time() - started) * 1000))

    def execute_method(
        self,
        method: MethodDraft,
        *,
        extra_tables: dict[str, list[dict[str, Any]]] | None = None,
    ) -> MockDryRunResult:
        """Execute the current MethodDraft through the existing mock path."""
        return run_simulated_real_execution(method, extra_tables=extra_tables)

    def _execute_plan(self, plan: QueryPlan) -> list[dict[str, Any]]:
        # 获取该表的 mock 数据
        table_data = _MOCK_DATA.get(plan.table, [])
        if not table_data:
            return []

        if plan.intent == Intent.count_distinct:
            values = {row.get(plan.group_by or "") for row in table_data if row.get(plan.group_by or "")}
            return [{"group_count": len(values)}]

        if plan.intent == Intent.latest_by_group:
            group = plan.group_by or ""
            latest: dict[Any, dict[str, Any]] = {}
            for row in table_data:
                key = row.get(group)
                if key is None:
                    continue
                # 使用任意时间字段或 id 来排序
                time_field = plan.time_field or "id"
                current = latest.get(key)
                if current is None or str(row.get(time_field, "")) > str(current.get(time_field, "")):
                    latest[key] = row
            return [latest[key] for key in sorted(latest)]

        if plan.intent in {Intent.top_n, Intent.aggregate_by_group}:
            metric = plan.metrics[0]
            alias = metric.alias or f"{metric.op}_{metric.field}"
            totals: dict[Any, float] = {}
            for row in table_data:
                if not self._matches_filters(row, plan):
                    continue
                key = row.get(plan.group_by or "")
                totals[key] = totals.get(key, 0.0) + float(row.get(metric.field) or 0)
            ordered = sorted(totals.items(), key=lambda item: item[1], reverse=True)
            return [{"group_key": key, alias: value} for key, value in ordered[: plan.limit]]

        # 默认：返回表的所有数据（可选过滤）
        result = []
        for row in table_data:
            if self._matches_filters(row, plan):
                result.append(row)
        return result[:plan.limit] if plan.limit else result

    @staticmethod
    def _matches_filters(row: dict[str, Any], plan: QueryPlan) -> bool:
        for filter_ in plan.filters:
            value = row.get(filter_.field)
            if filter_.op == "in" and value not in filter_.value:
                return False
            if filter_.op == "=" and isinstance(value, str) and isinstance(filter_.value, str):
                # Match the production customer-name lookup contract: labels
                # are case-insensitive and tolerant of omitted spaces.
                normalize = lambda item: "".join(str(item).casefold().split())
                if normalize(value) != normalize(filter_.value):
                    return False
            elif filter_.op == "=" and value != filter_.value:
                return False
            if filter_.op == "!=" and value == filter_.value:
                return False
            if filter_.op == "like" and filter_.value not in str(value):
                return False
        return True
