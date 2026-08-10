from __future__ import annotations

import re
from typing import Any

from finance_agent.harness.plan_schema import Intent, QueryPlan
from finance_agent.metadata.policy import Policy


class SqlBuildError(ValueError):
    pass


def quote_ident(identifier: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", identifier):
        raise SqlBuildError(f"invalid SQL identifier: {identifier}")
    return identifier


def literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "(" + ", ".join(literal(item) for item in value) + ")"
    return "'" + str(value).replace("'", "''") + "'"


def where_clause(plan: QueryPlan) -> str:
    parts: list[str] = []
    for filter_ in plan.filters:
        field = quote_ident(filter_.field)
        if filter_.op == "in":
            parts.append(f"{field} IN {literal(filter_.value)}")
        elif filter_.op == "between":
            if not isinstance(filter_.value, list) or len(filter_.value) != 2:
                raise SqlBuildError("between filter requires a two-item list")
            parts.append(f"{field} BETWEEN {literal(filter_.value[0])} AND {literal(filter_.value[1])}")
        else:
            parts.append(f"{field} {filter_.op} {literal(filter_.value)}")
    return "WHERE " + " AND ".join(parts) if parts else ""


def build_sql(plan: QueryPlan, policy: Policy) -> str:
    table = quote_ident(plan.table)
    limit = min(plan.limit, policy.max_rows)
    where_sql = where_clause(plan)

    if plan.intent == Intent.count_distinct:
        group = quote_ident(plan.group_by or "")
        return f"SELECT COUNT(DISTINCT {group}) AS group_count FROM {table} {where_sql}".strip()

    if plan.intent == Intent.latest_by_group:
        group = quote_ident(plan.group_by or "")
        order = ", ".join(f"{quote_ident(item.field)} {item.direction.upper()} NULLS LAST" for item in plan.order_by)
        if not order:
            raise SqlBuildError("latest_by_group requires order_by")
        selected = [group, "id", "id_no", "account_id", "card_id", "type", "status", "total_amount", "settle_amount", "origin_amount", "currency", "transaction_at", "complete_at", "channel_complete_at", "created_at"]
        select_expr = ", ".join(dict.fromkeys(quote_ident(name) for name in selected))
        null_filter = f"{group} IS NOT NULL"
        combined_where = f"WHERE {null_filter}" if not where_sql else f"{where_sql} AND {null_filter}"
        return (
            "WITH ranked AS ("
            f"SELECT {select_expr}, ROW_NUMBER() OVER (PARTITION BY {group} ORDER BY {order}) AS rn "
            f"FROM {table} {combined_where}"
            f") SELECT {select_expr} FROM ranked WHERE rn = 1 ORDER BY {group} LIMIT {limit}"
        )

    if plan.intent in {Intent.top_n, Intent.aggregate_by_group}:
        if not plan.metrics:
            raise SqlBuildError(f"{plan.intent.value} requires metrics")
        group = quote_ident(plan.group_by or "")
        metric = plan.metrics[0]
        metric_field = quote_ident(metric.field)
        alias = quote_ident(metric.alias or f"{metric.op}_{metric.field}")
        op = metric.op.upper()
        order = plan.order_by[0] if plan.order_by else None
        order_field = quote_ident(order.field) if order else alias
        order_direction = order.direction.upper() if order else "DESC"
        return (
            f"SELECT {group} AS group_key, {op}(COALESCE({metric_field}, 0)) AS {alias} "
            f"FROM {table} {where_sql} "
            f"GROUP BY {group} ORDER BY {order_field} {order_direction} LIMIT {limit}"
        ).strip()

    raise SqlBuildError(f"unsupported intent: {plan.intent.value}")


def assert_readonly_sql(sql: str, policy: Policy) -> None:
    stripped = sql.strip()
    first = stripped.split(None, 1)[0].lower()
    if first not in {"select", "with"}:
        raise SqlBuildError("only SELECT/WITH read-only SQL is allowed")
    forbidden = "|".join(re.escape(word) for word in policy.forbidden_sql_keywords)
    if forbidden and re.search(rf"\b({forbidden})\b", stripped, re.I):
        raise SqlBuildError("forbidden SQL keyword detected")
