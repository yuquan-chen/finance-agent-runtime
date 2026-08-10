from __future__ import annotations

import re
import sqlite3
from typing import Any

from finance_agent.harness.analysis_schema import MethodDraft


class SandboxSqlError(RuntimeError):
    pass


def run_sql_method(
    method: MethodDraft,
    rows: list[dict[str, Any]],
    extra_tables: dict[str, list[dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    if not method.sql_template:
        raise SandboxSqlError("sql method has no sql_template")

    sql = _prepare_sql(method.sql_template)
    table = method.table
    extra = extra_tables or {}
    with sqlite3.connect(":memory:") as connection:
        connection.row_factory = sqlite3.Row
        # Skip primary table load if extra_tables already provides it
        if table not in extra:
            _load_table(connection, table, rows)
        for extra_name, extra_rows in extra.items():
            _load_table(connection, extra_name, extra_rows)
        cursor = connection.execute(sql)
        return [dict(row) for row in cursor.fetchall()]


def _prepare_sql(sql: str) -> str:
    prepared = sql.strip().rstrip(";")
    if not re.match(r"^(select|with)\b", prepared, re.I):
        raise SandboxSqlError("sandbox sql runner only accepts SELECT/WITH")

    # MVP synthetic execution does not yet expose a time-range UI. Replace
    # named params with broad constants so the SQL still executes in sandbox.
    prepared = prepared.replace(":start_time", "'0000-01-01T00:00:00'")
    prepared = prepared.replace(":end_time", "'9999-12-31T23:59:59'")
    prepared = re.sub(r"DATE_TRUNC\('month',\s*([A-Za-z_][A-Za-z0-9_]*)\)", r"substr(\1, 1, 7)", prepared, flags=re.I)
    prepared = re.sub(r"DATE_TRUNC\('day',\s*([A-Za-z_][A-Za-z0-9_]*)\)", r"substr(\1, 1, 10)", prepared, flags=re.I)
    return prepared


def _load_table(connection: sqlite3.Connection, table: str, rows: list[dict[str, Any]]) -> None:
    columns = _columns(rows)
    column_defs = ", ".join(f"{_quote_identifier(column)} {_sqlite_type(rows, column)}" for column in columns)
    connection.execute(f"CREATE TABLE {_quote_identifier(table)} ({column_defs})")
    if not rows:
        return
    placeholders = ", ".join("?" for _ in columns)
    column_sql = ", ".join(_quote_identifier(column) for column in columns)
    insert_sql = f"INSERT INTO {_quote_identifier(table)} ({column_sql}) VALUES ({placeholders})"
    values = [tuple(row.get(column) for column in columns) for row in rows]
    connection.executemany(insert_sql, values)


def _columns(rows: list[dict[str, Any]]) -> list[str]:
    ordered: list[str] = []
    for row in rows:
        for key in row:
            if key not in ordered:
                ordered.append(key)
    if not ordered:
        return ["id"]
    return ordered


def _sqlite_type(rows: list[dict[str, Any]], column: str) -> str:
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


def _quote_identifier(identifier: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", identifier):
        raise SandboxSqlError(f"invalid identifier: {identifier}")
    return f'"{identifier}"'
