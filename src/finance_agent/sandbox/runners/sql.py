"""SQL Runner — 在进程内 SQLite 内存库中执行只读 mock SQL。"""
from __future__ import annotations

import json
import re
import sqlite3
from contextlib import closing
from typing import Any

from finance_agent.executor.sql_parameters import normalize_sql_template
from finance_agent.sandbox.provider import SandboxExecutionRequest
from finance_agent.sandbox.runner_registry import register_runner


class SandboxSqlError(RuntimeError):
    pass


@register_runner("sql")
def run_sql(request: SandboxExecutionRequest) -> list[dict[str, Any]]:
    """执行 SQL 方法，不连接任何外部数据库。"""
    method = request.method
    if not method.sql_template:
        raise SandboxSqlError("sql method has no sql_template")

    sql_query, params = _prepare_sql(method.sql_template, method.params, dialect="sqlite")
    table = method.table
    extra = request.extra_tables or {}

    conn = sqlite3.connect(":memory:")
    conn.create_function("DATE_TRUNC", 2, _sqlite_date_trunc)
    try:
        with closing(conn.cursor()) as cursor:
            # 加载数据到进程内临时表；extra_tables 只提供本次方法需要的本地样本。
            if table not in extra:
                _load_table(cursor, table, request.rows)
            for extra_name, extra_rows in extra.items():
                _load_table(cursor, extra_name, extra_rows)

            # 执行查询（使用参数绑定）
            if params:
                cursor.execute(sql_query, params)
            else:
                cursor.execute(sql_query)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()

            # 转换为字典列表
            result = []
            for row in rows:
                row_dict = {}
                for i, value in enumerate(row):
                    # 处理特殊类型
                    row_dict[columns[i]] = value
                result.append(row_dict)

            return result
    finally:
        conn.close()


def _prepare_sql(
    sql: str,
    params: dict[str, Any] | None = None,
    *,
    dialect: str = "postgres",
) -> tuple[str, dict[str, Any]]:
    """准备 SQL 语句。

    返回 (sql, params) 元组：
    - sql: 参数化的 SQL，使用 %s 占位符
    - params: 参数值字典

    默认保留 PostgreSQL 占位符，供 direct-db 兼容性测试使用；mock
    runner 传入 ``dialect="sqlite"``，从而完全在本地内存库执行。
    """
    prepared = sql.strip().rstrip(";")

    # 安全检查：只允许 SELECT/WITH
    if not re.match(r"^(select|with)\b", prepared, re.IGNORECASE):
        raise SandboxSqlError("sandbox sql runner only accepts SELECT/WITH")

    # 处理 PostgreSQL 日期函数
    # DATE_TRUNC('year', CURRENT_DATE - INTERVAL '1 year') → 一年前的日期
    prepared = re.sub(
        r"DATE_TRUNC\('year',\s*CURRENT_DATE\s*-\s*INTERVAL\s+'(\d+)\s+year'\)",
        r"DATE_TRUNC('year', CURRENT_DATE - INTERVAL '\1 year')",
        prepared,
        flags=re.IGNORECASE
    )

    # Keep driver-specific placeholder conversion below, but share all
    # user-facing SQL semantics with the direct DB executor.
    prepared, prepared_params = normalize_sql_template(prepared, params)

    # 提取命名参数并转换为 psycopg2 格式
    # :param_name → %(param_name)s，并收集参数值
    param_values = {}

    def _replace_param(match):
        param_name = match.group(1)
        if param_name in prepared_params:
            param_values[param_name] = prepared_params[param_name]
            return f"%({param_name})s" if dialect == "postgres" else f":{param_name}"
        else:
            # 没有提供参数值，使用 NULL
            return "NULL"

    # 使用负向后行断言 (?<!:) 排除 PostgreSQL 的 ::type 类型转换语法
    prepared = re.sub(r"(?<!:):([a-zA-Z_][a-zA-Z0-9_]*)", _replace_param, prepared)

    # 处理各种与 NULL 的比较
    # != NULL → IS NOT NULL（先处理，避免被其他规则误匹配）
    prepared = re.sub(r"!=\s*NULL", "IS NOT NULL", prepared)
    prepared = re.sub(r"<>\s*NULL", "IS NOT NULL", prepared)
    # >= NULL, <= NULL, > NULL, < NULL → IS NULL（与 NULL 比较结果为 NULL，改为 IS NULL 保证语法正确）
    prepared = re.sub(r">=\s*NULL", "IS NULL", prepared)
    prepared = re.sub(r"<=\s*NULL", "IS NULL", prepared)
    prepared = re.sub(r">\s*NULL", "IS NULL", prepared)
    prepared = re.sub(r"<\s*NULL", "IS NULL", prepared)
    # = NULL → IS NULL
    prepared = re.sub(r"=\s*NULL", "IS NULL", prepared)

    if dialect == "sqlite":
        # normalize_sql_template uses PostgreSQL's regexp_replace/ILIKE for
        # business-name matching. SQLite mock data only needs equivalent
        # whitespace-tolerant matching for local tests.
        prepared = re.sub(r"\bILIKE\b", "LIKE", prepared, flags=re.IGNORECASE)
        prepared = re.sub(
            r"regexp_replace\(([^(),]+),\s*'\\s\+',\s*'',\s*'g'\)",
            r"replace(\1, ' ', '')",
            prepared,
            flags=re.IGNORECASE,
        )
        prepared = re.sub(
            r"CURRENT_DATE\s*-\s*INTERVAL\s*'([0-9]+)\s+year'",
            r"date('now', '-\1 year')",
            prepared,
            flags=re.IGNORECASE,
        )

    return prepared, param_values


def _load_table(cursor, table: str, rows: list[dict[str, Any]]) -> None:
    """加载数据到 SQLite 临时表。"""
    if not rows:
        return

    # 删除已存在的临时表
    cursor.execute(f"DROP TABLE IF EXISTS {_quote_identifier(table)}")

    # 获取列名
    columns = _columns(rows)

    # 构建列定义
    column_defs = []
    for column in columns:
        # Mock rows are intentionally partial fixtures, not a copy of the
        # production table. Infer their temporary-table types from values so
        # a refreshed production catalog cannot invalidate mock data.
        sqlite_type = _sqlite_type(rows, column)
        column_defs.append(f"{_quote_identifier(column)} {sqlite_type}")

    # 创建表
    cursor.execute(f"CREATE TABLE {_quote_identifier(table)} ({', '.join(column_defs)})")

    # 插入数据
    placeholders = ", ".join(["?"] * len(columns))
    column_sql = ", ".join(_quote_identifier(column) for column in columns)
    insert_sql = f"INSERT INTO {_quote_identifier(table)} ({column_sql}) VALUES ({placeholders})"

    values = [tuple(_sqlite_value(row.get(column)) for column in columns) for row in rows]
    cursor.executemany(insert_sql, values)


def _columns(rows: list[dict[str, Any]]) -> list[str]:
    """获取所有列名。"""
    ordered: list[str] = []
    for row in rows:
        for key in row:
            if key not in ordered:
                ordered.append(key)
    if not ordered:
        return ["id"]
    return ordered


def _sqlite_type(rows: list[dict[str, Any]], column: str) -> str:
    """根据本地样本推断 SQLite 临时列类型。"""
    for row in rows:
        value = row.get(column)
        if value is None:
            continue
        if isinstance(value, bool):
            return "INTEGER"
        if isinstance(value, int):
            return "INTEGER"
        if isinstance(value, float):
            return "REAL"
        return "TEXT"
    return "TEXT"


def _sqlite_value(value: Any) -> Any:
    """将 JSON、数组和日期等值转换为 SQLite 可绑定的类型。"""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if hasattr(value, "isoformat") and not isinstance(value, (str, bytes)):
        return value.isoformat()
    return value


def _sqlite_date_trunc(grain: Any, value: Any) -> str | None:
    """Provide the small DATE_TRUNC subset used by generated mock SQL."""
    if value is None:
        return None
    text = str(value)
    normalized_grain = str(grain).lower()
    if normalized_grain == "year":
        return f"{text[:4]}-01-01"
    if normalized_grain == "month":
        return f"{text[:7]}-01"
    if normalized_grain == "day":
        return text[:10]
    return text


def _quote_identifier(identifier: str) -> str:
    """引用标识符。"""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", identifier):
        raise SandboxSqlError(f"invalid identifier: {identifier}")
    return f'"{identifier}"'
