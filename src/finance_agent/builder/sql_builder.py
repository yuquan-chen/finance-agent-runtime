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
    """深度安全检查：验证 SQL 只包含只读操作。

    检查策略：
    1. 第一个词必须是 SELECT 或 WITH
    2. 禁止危险关键词和函数（包括子查询、CTE 中的调用）
    3. 禁止访问系统表/视图
    4. 禁止注释中的危险内容
    """
    stripped = sql.strip()

    # 1. 检查第一个词
    first = stripped.split(None, 1)[0].lower()
    if first not in {"select", "with"}:
        raise SqlBuildError("only SELECT/WITH read-only SQL is allowed")

    # 2. 移除注释，避免绕过检查
    # 移除单行注释 (-- ...)
    no_comments = re.sub(r'--[^\n]*', '', stripped)
    # 移除多行注释 (/* ... */)
    no_comments = re.sub(r'/\*.*?\*/', '', no_comments, flags=re.DOTALL)

    # 3. 检查危险关键词和函数
    forbidden = "|".join(re.escape(word) for word in policy.forbidden_sql_keywords)
    if forbidden and re.search(rf"\b({forbidden})\b", no_comments, re.I):
        raise SqlBuildError("forbidden SQL keyword detected")

    # 4. 检查危险的函数调用模式（函数名后跟括号）
    dangerous_functions = [
        r'\bpg_read_file\s*\(',
        r'\bpg_write_file\s*\(',
        r'\bpg_read_binary_file\s*\(',
        r'\blo_import\s*\(',
        r'\blo_export\s*\(',
        r'\bpg_ls_dir\s*\(',
        r'\bpg_stat_file\s*\(',
        r'\bpg_sleep\s*\(',
        r'\bpg_sleep_for\s*\(',
        r'\bpg_sleep_until\s*\(',
        r'\bdblink\s*\(',
        r'\bdblink_exec\s*\(',
        r'\bdblink_connect\s*\(',
        r'\bdblink_open\s*\(',
        r'\bdblink_fetch\s*\(',
        r'\bdblink_close\s*\(',
        r'\bdblink_disconnect\s*\(',
        r'\bcopy\s+.*\bto\b',  # COPY ... TO (文件操作)
        r'\bcopy\s+.*\bfrom\b',  # COPY ... FROM (文件操作)
    ]
    for pattern in dangerous_functions:
        if re.search(pattern, no_comments, re.I):
            raise SqlBuildError(f"dangerous function call detected: {pattern}")

    # 5. 检查系统表/视图访问
    system_tables = [
        r'\bpg_stat_activity\b',
        r'\bpg_stat_replication\b',
        r'\bpg_stat_wal_receiver\b',
        r'\bpg_stat_ssl\b',
        r'\bpg_stat_progress\b',
        r'\bpg_user\b',
        r'\bpg_shadow\b',
        r'\bpg_group\b',
        r'\bpg_roles\b',
        r'\bpg_authid\b',
        r'\bpg_auth_members\b',
    ]
    for pattern in system_tables:
        if re.search(pattern, no_comments, re.I):
            raise SqlBuildError(f"system table access detected: {pattern}")

    # 6. 检查危险的字符串模式
    dangerous_patterns = [
        r"'\s*/etc/",  # 路径访问
        r"'\s*/tmp/",
        r"'\s*/var/",
        r"'\s*[A-Za-z]:\\",
    ]
    for pattern in dangerous_patterns:
        if re.search(pattern, no_comments, re.I):
            raise SqlBuildError(f"dangerous path pattern detected")
