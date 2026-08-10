"""SQL Runner — 在 PostgreSQL 中执行只读 SQL。"""
from __future__ import annotations

import re
from typing import Any

import psycopg2

from finance_agent.config import get_settings
from finance_agent.metadata.table_registry import get_default_table_registry
from finance_agent.sandbox.provider import SandboxExecutionRequest
from finance_agent.sandbox.runner_registry import register_runner


class SandboxSqlError(RuntimeError):
    pass


def _get_connection():
    """获取 PostgreSQL 连接。"""
    settings = get_settings()
    try:
        conn = psycopg2.connect(
            host=settings.pg_host,
            port=settings.pg_port,
            database=settings.pg_database,
            user=settings.pg_user,
            password=settings.pg_password,
        )
        conn.autocommit = True
        return conn
    except psycopg2.Error as e:
        raise SandboxSqlError(f"Failed to connect to PostgreSQL: {e}")


@register_runner("sql")
def run_sql(request: SandboxExecutionRequest) -> list[dict[str, Any]]:
    """执行 SQL 方法。"""
    method = request.method
    if not method.sql_template:
        raise SandboxSqlError("sql method has no sql_template")

    sql_query, params = _prepare_sql(method.sql_template, method.params)
    table = method.table
    extra = request.extra_tables or {}

    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            # 加载数据到临时表
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
                    if isinstance(value, memoryview):
                        row_dict[columns[i]] = bytes(value).hex()
                    else:
                        row_dict[columns[i]] = value
                result.append(row_dict)

            return result
    finally:
        conn.close()


def _prepare_sql(sql: str, params: dict[str, Any] | None = None) -> tuple[str, dict[str, Any]]:
    """准备 SQL 语句（PostgreSQL 原生语法）。

    返回 (sql, params) 元组：
    - sql: 参数化的 SQL，使用 %s 占位符
    - params: 参数值字典
    """
    prepared = sql.strip().rstrip(";")

    # 安全检查：只允许 SELECT/WITH
    if not re.match(r"^(select|with)\b", prepared, re.I):
        raise SandboxSqlError("sandbox sql runner only accepts SELECT/WITH")

    # 处理 PostgreSQL 日期函数
    # DATE_TRUNC('year', CURRENT_DATE - INTERVAL '1 year') → 一年前的日期
    prepared = re.sub(
        r"DATE_TRUNC\('year',\s*CURRENT_DATE\s*-\s*INTERVAL\s+'(\d+)\s+year'\)",
        r"DATE_TRUNC('year', CURRENT_DATE - INTERVAL '\1 year')",
        prepared,
        flags=re.I
    )

    # 把 = 改成 ILIKE（不区分大小写），用于字符串比较
    # 例如：WHERE legal_name = :customer_name → WHERE legal_name ILIKE :customer_name
    prepared = re.sub(r"(\w+)\s*=\s*(:[a-zA-Z_][a-zA-Z0-9_]*)", r"\1 ILIKE \2", prepared)

    # 参数值模糊处理：在字母和数字之间插入 %，并用 % 包裹
    # 例如：'Company5' → '%Company%5%'，可以匹配 'Company 5'
    if params:
        for key in params:
            if isinstance(params[key], str):
                val = params[key]
                # 在字母→数字、数字→字母之间插入 %
                val = re.sub(r"([a-zA-Z])(\d)", r"\1%\2", val)
                val = re.sub(r"(\d)([a-zA-Z])", r"\1%\2", val)
                # 用 % 包裹，实现模糊匹配
                params[key] = f"%{val}%"

    # 提取命名参数并转换为 psycopg2 格式
    # :param_name → %(param_name)s，并收集参数值
    param_values = {}

    def _replace_param(match):
        param_name = match.group(1)
        if params and param_name in params:
            param_values[param_name] = params[param_name]
            return f"%({param_name})s"
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

    return prepared, param_values


def _load_table(cursor, table: str, rows: list[dict[str, Any]]) -> None:
    """加载数据到 PostgreSQL 临时表。"""
    if not rows:
        return

    # 删除已存在的临时表
    cursor.execute(f"DROP TABLE IF EXISTS {_quote_identifier(table)}")

    # 获取列名
    columns = _columns(rows)

    # 尝试从 schema 获取字段类型
    schema_types = _get_schema_types(table)

    # 构建列定义
    column_defs = []
    for column in columns:
        if column in schema_types:
            pg_type = _schema_type_to_pg(schema_types[column])
        else:
            pg_type = _pg_type(rows, column)
        column_defs.append(f"{_quote_identifier(column)} {pg_type}")

    # 创建表
    cursor.execute(f"CREATE TABLE {_quote_identifier(table)} ({', '.join(column_defs)})")

    # 插入数据
    placeholders = ", ".join(["%s"] * len(columns))
    column_sql = ", ".join(_quote_identifier(column) for column in columns)
    insert_sql = f"INSERT INTO {_quote_identifier(table)} ({column_sql}) VALUES ({placeholders})"

    values = [tuple(row.get(column) for column in columns) for row in rows]
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


def _pg_type(rows: list[dict[str, Any]], column: str) -> str:
    """推断 PostgreSQL 列类型。"""
    # 时间字段后缀
    time_suffixes = ("_at", "_time", "_date", "_datetime", "_timestamp")

    for row in rows:
        value = row.get(column)
        if value is None:
            continue
        if isinstance(value, bool):
            return "BOOLEAN"
        if isinstance(value, int):
            return "BIGINT"
        if isinstance(value, float):
            return "NUMERIC"
        if isinstance(value, dict):
            return "JSONB"
        if isinstance(value, list):
            return "JSONB"
        if isinstance(value, str):
            # 检查是否是时间字段（通过字段名）
            if column.lower().endswith(time_suffixes):
                return "TIMESTAMPTZ"
            # 检查是否是 ISO 格式的时间字符串
            if re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", value):
                return "TIMESTAMPTZ"
            return "TEXT"
    return "TEXT"


def _quote_identifier(identifier: str) -> str:
    """引用标识符。"""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", identifier):
        raise SandboxSqlError(f"invalid identifier: {identifier}")
    return f'"{identifier}"'


def _get_schema_types(table: str) -> dict[str, str]:
    """从 schema 中获取表的字段类型。"""
    try:
        registry = get_default_table_registry()
        table_meta = registry.get(table)
        if table_meta:
            return {col.name: col.type for col in table_meta.columns}
    except Exception:
        pass
    return {}


def _schema_type_to_pg(schema_type: str) -> str:
    """将 schema 类型转换为 PostgreSQL 类型。"""
    type_mapping = {
        "varchar": "VARCHAR",
        "text": "TEXT",
        "bigint": "BIGINT",
        "int": "INTEGER",
        "integer": "INTEGER",
        "numeric": "NUMERIC",
        "float": "REAL",
        "double": "DOUBLE PRECISION",
        "boolean": "BOOLEAN",
        "bool": "BOOLEAN",
        "json": "JSONB",
        "jsonb": "JSONB",
        "timestamptz": "TIMESTAMPTZ",
        "timestamp": "TIMESTAMP",
        "date": "DATE",
        "time": "TIME",
        "uuid": "UUID",
    }
    return type_mapping.get(schema_type.lower(), "TEXT")
