"""Method Draft 生成器（声明型）。

LLM 在 AnalysisStep 中提供 sql 字段，本模块将其转换为 MethodDraft。
如果 step 没有 sql，说明 LLM 没有写 SQL，会报错触发 repair。
"""
from __future__ import annotations

import re
from typing import Any

from finance_agent.harness.analysis_schema import AnalysisPlan, AnalysisStep, MethodDraft
from finance_agent.operations.handler_registry import (
    OperationHandlerRegistry,
    get_default_registry,
)


def generate_method_draft(plan: AnalysisPlan, registry: OperationHandlerRegistry | None = None) -> MethodDraft:
    registry = registry or get_default_registry()
    step = _choose_primary_step(plan)
    return generate_method_draft_for_step(plan.goal, step, registry)


def generate_method_drafts(plan: AnalysisPlan, registry: OperationHandlerRegistry | None = None) -> list[MethodDraft]:
    registry = registry or get_default_registry()
    steps = plan.steps or [_choose_primary_step(plan)]
    return [generate_method_draft_for_step(plan.goal, step, registry) for step in steps]


def generate_dependent_method(
    goal: str,
    operation: str,
    prior_result_schema: dict[str, Any],
    result_ref: str,
    registry: OperationHandlerRegistry | None = None,
) -> MethodDraft:
    """Generate a method that operates on a prior result (loaded as 'prior_result' table)."""
    registry = registry or get_default_registry()
    columns = prior_result_schema.get("columns", [])
    column_names = [col["name"] if isinstance(col, dict) else str(col) for col in columns]

    # 根据操作类型生成 SQL
    sql = _dependent_sql(operation, column_names)
    return MethodDraft(
        method_type="sql",
        name=f"dependent_{operation}",
        goal=goal,
        operation=operation or "group_by",
        table="prior_result",
        data_source="result_ref",
        result_ref=result_ref,
        required_fields=[f"prior_result.{column_names[0]}"] if column_names else [],
        sql_template=sql,
        output_schema={"rows": "list"},
        logic_summary=[f"基于之前的结果，执行 {operation} 操作"],
    )


def _dependent_sql(operation: str, column_names: list[str]) -> str:
    """根据操作类型生成依赖方法的 SQL。"""
    if not column_names:
        return "SELECT * FROM prior_result LIMIT 100"

    # 找分组字段（非数值字段）
    group_by = column_names[0]
    for col in column_names:
        if col not in ("count", "total", "amount", "value", "mean", "variance"):
            group_by = col
            break

    # 找数值字段
    metric = None
    for col in column_names:
        if col in ("total_amount", "settle_amount", "origin_amount", "amount", "value", "total"):
            metric = col
            break
    if not metric and len(column_names) > 1:
        metric = column_names[1] if column_names[1] != group_by else column_names[0]

    if operation in ("status_distribution", "distribution"):
        dimension = group_by
        return f"SELECT {dimension}, COUNT(*) AS count FROM prior_result GROUP BY {dimension} ORDER BY count DESC, {dimension} ASC"

    if operation == "trend":
        time_field = next((col for col in column_names if "date" in col or "time" in col or "at" in col), column_names[0])
        return f"SELECT substr({time_field}, 1, 7) AS bucket, SUM(COALESCE({metric or column_names[0]}, 0)) AS total_value FROM prior_result GROUP BY bucket ORDER BY bucket ASC"

    if operation == "variance":
        m = metric or column_names[0]
        return f"SELECT COUNT(*) AS count, AVG({m}) AS mean, AVG({m} * {m}) - AVG({m}) * AVG({m}) AS variance FROM prior_result WHERE {m} IS NOT NULL"

    # top_n / group_by / 默认
    m = metric or column_names[-1] if len(column_names) > 1 else column_names[0]
    if group_by == m:
        return f"SELECT {group_by}, COUNT(*) AS count FROM prior_result GROUP BY {group_by} ORDER BY count DESC LIMIT 10"
    return f"SELECT {group_by}, SUM(COALESCE({m}, 0)) AS {m} FROM prior_result GROUP BY {group_by} ORDER BY {m} DESC LIMIT 10"


def generate_method_draft_for_step(goal: str, step: AnalysisStep, registry: OperationHandlerRegistry | None = None) -> MethodDraft:
    registry = registry or get_default_registry()

    # LLM 提供了 Python 代码 → 直接用
    if step.code:
        return MethodDraft(
            method_type="code",
            name=f"llm_{step.operation}_code",
            goal=goal,
            operation=step.operation,
            table=step.table,
            data_source="table",
            code=step.code,
            required_fields=_extract_fields_from_code(step.code),
            output_schema={"rows": "list"},
            logic_summary=[f"LLM 自写代码: {step.operation}"],
        )

    # LLM 提供了 SQL → 直接用
    if step.sql:
        return MethodDraft(
            method_type="sql",
            name=f"llm_{step.operation}",
            goal=goal,
            operation=step.operation,
            table=step.table,
            data_source="table",
            sql_template=step.sql,
            required_fields=_extract_fields_from_sql(step.sql, step.table),
            output_schema={"rows": "list"},
            logic_summary=[f"LLM 自写 SQL: {step.operation}"],
        )

    # LLM 没写 SQL → 从 step 元数据生成兜底 SQL
    sql = _fallback_sql(step)
    return MethodDraft(
        method_type="sql",
        name=f"fallback_{step.operation}",
        goal=goal,
        operation=step.operation,
        table=step.table,
        data_source="table",
        sql_template=sql,
        required_fields=_extract_fields_from_sql(sql, step.table),
        output_schema={"rows": "list"},
        logic_summary=[f"兜底 SQL: {step.operation}"],
    )


def _choose_primary_step(plan: AnalysisPlan) -> AnalysisStep:
    if not plan.steps:
        return AnalysisStep(operation="top_n", metric="total_amount", group_by="account_id")
    return plan.steps[0]


def _fallback_sql(step: AnalysisStep) -> str:
    """从 step 元数据生成兜底 SQL（当 LLM 没有提供 sql 时）。"""
    table = step.table
    operation = step.operation

    if operation in ("status_distribution", "distribution"):
        dimension = step.dimension or step.group_by or "status"
        return f"SELECT {dimension}, COUNT(*) AS count FROM {table} GROUP BY {dimension} ORDER BY count DESC, {dimension} ASC"

    if operation == "trend":
        metric = step.metric or "total_amount"
        time_field = step.time_field or "transaction_at"
        grain = step.grain or "month"
        bucket = f"substr({time_field}, 1, 7)" if grain == "month" else f"substr({time_field}, 1, 10)"
        return f"SELECT {bucket} AS bucket, SUM(COALESCE({metric}, 0)) AS {metric} FROM {table} GROUP BY bucket ORDER BY bucket ASC"

    if operation == "variance":
        metric = step.metric or "total_amount"
        return f"SELECT COUNT(*) AS count, AVG({metric}) AS mean, AVG({metric} * {metric}) - AVG({metric}) * AVG({metric}) AS variance FROM {table} WHERE {metric} IS NOT NULL"

    # top_n / group_by / 默认
    metric = step.metric or "total_amount"
    group_by = step.group_by or step.dimension or "account_id"
    limit = step.limit or 10
    return f"SELECT {group_by}, SUM(COALESCE({metric}, 0)) AS {metric} FROM {table} GROUP BY {group_by} ORDER BY {metric} DESC LIMIT {limit}"


def _extract_fields_from_sql(sql: str, table: str) -> list[str]:
    """从 SQL 中提取 table.field 格式的字段引用（粗略提取）。"""
    patterns = re.findall(r"(?:FROM|JOIN)\s+(\w+)", sql, re.IGNORECASE)
    detected_table = patterns[0] if patterns else table
    select_match = re.search(r"SELECT\s+(.*?)\s+FROM", sql, re.IGNORECASE | re.DOTALL)
    if not select_match:
        return []
    fields = []
    # 聚合函数和表达式模式，需要跳过
    agg_pattern = re.compile(r"(?i)^(COUNT|SUM|AVG|MIN|MAX|COALESCE|CASE|WHEN|THEN|ELSE|END|substr)\s*\(|^\*|^\(|^\d")
    for part in select_match.group(1).split(","):
        part = part.strip()
        # 去掉 AS 别名
        part = re.sub(r"\s+AS\s+\w+", "", part, flags=re.IGNORECASE).strip()
        # 跳过聚合函数、表达式、字面量
        if agg_pattern.match(part):
            continue
        if "." in part:
            fields.append(part)
        elif part and not part.startswith("*") and not part.startswith("("):
            fields.append(f"{detected_table}.{part}")
    return fields


def _extract_fields_from_code(code: str) -> list[str]:
    """从 Python 代码中提取字段引用（粗略提取）。

    查找类似 row["field_name"] 或 row.get("field_name") 的模式。
    """
    fields = []
    # 匹配 row["field"] 或 row['field']
    pattern = r'''row\[['"](\w+(?:\.\w+)?)['"]\]'''
    matches = re.findall(pattern, code)
    fields.extend(matches)
    # 匹配 row.get("field") 或 row.get('field')
    pattern = r'''row\.get\(['"](\w+(?:\.\w+)?)['"]\]'''
    matches = re.findall(pattern, code)
    fields.extend(matches)
    # 去重
    return list(dict.fromkeys(fields))
