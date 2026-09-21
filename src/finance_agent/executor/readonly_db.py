from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import create_engine, text

from finance_agent.builder.sql_builder import assert_readonly_sql
from finance_agent.executor.sql_parameters import normalize_sql_template
from finance_agent.harness.analysis_schema import MethodDraft, MockDryRunResult
from finance_agent.metadata.policy import Policy
from finance_agent.query.safe_requests import SafeQueryRegistry, SafeQueryRequest


@dataclass(frozen=True)
class QueryResult:
    rows: list[dict[str, Any]]
    row_count: int
    elapsed_ms: int


class ReadonlyDbExecutor:
    def __init__(self, database_url: str, policy: Policy):
        self.database_url = database_url
        self.policy = policy
        self.engine = create_engine(database_url, pool_pre_ping=True) if database_url else None

    def execute(self, sql: str, plan: Any | None = None, params: dict[str, Any] | None = None) -> QueryResult:
        if self.engine is None:
            raise RuntimeError("DATABASE_URL is not configured")
        normalized_sql, normalized_params = normalize_sql_template(sql, params)
        assert_readonly_sql(normalized_sql, self.policy)
        started = time.time()
        with self.engine.begin() as connection:
            self._configure_readonly_transaction(connection)
            rows = self._execute_query(connection, normalized_sql, normalized_params)
        return QueryResult(rows=rows, row_count=len(rows), elapsed_ms=int((time.time() - started) * 1000))

    def execute_safe_request(self, request: SafeQueryRequest, registry: SafeQueryRegistry) -> QueryResult:
        """Execute an allowlisted request without accepting caller-supplied SQL."""
        definition, params = registry.bind(request)
        return self.execute(definition.sql, params=params)

    def execute_method(
        self,
        method: MethodDraft,
        *,
        extra_tables: dict[str, list[dict[str, Any]]] | None = None,
    ) -> MockDryRunResult:
        if method.method_type != "sql" or not method.sql_template:
            return MockDryRunResult(
                status="failed",
                errors=["direct_db executor only supports SQL methods"],
                input_summary={"execution_mode": "direct_db", "real_database_used": True},
            )
        try:
            if extra_tables:
                result = self._execute_with_extra_tables(method, extra_tables)
            else:
                result = self.execute(method.sql_template, params=method.params)
        except Exception as exc:
            return MockDryRunResult(
                status="failed",
                errors=[f"{type(exc).__name__}: {exc}"],
                input_summary={
                    "runner": method.method_type,
                    "execution_mode": "direct_db",
                    "real_database_used": True,
                },
            )
        return MockDryRunResult(
            status="passed",
            output=result.rows,
            input_summary={
                "runner": method.method_type,
                "execution_mode": "direct_db",
                "real_database_used": True,
                "row_count": result.row_count,
                "elapsed_ms": result.elapsed_ms,
                "extra_tables": sorted(extra_tables or {}),
            },
        )

    def _configure_readonly_transaction(self, connection: Any) -> None:
        if connection.dialect.name != "postgresql":
            return
        connection.execute(text("SET TRANSACTION READ ONLY"))
        connection.execute(text(f"SET LOCAL statement_timeout = {int(self.policy.statement_timeout_ms)}"))

    def _execute_query(
        self,
        connection: Any,
        sql: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        result = connection.execute(text(sql), params or {})
        return [dict(row._mapping) for row in result.fetchmany(self.policy.max_rows)]

    def _execute_with_extra_tables(
        self,
        method: MethodDraft,
        extra_tables: dict[str, list[dict[str, Any]]],
    ) -> QueryResult:
        normalized_sql, normalized_params = normalize_sql_template(method.sql_template or "", method.params)
        assert_readonly_sql(normalized_sql, self.policy)
        started = time.time()
        with self.engine.begin() as connection:
            self._configure_readonly_transaction(connection)
            for table, rows in extra_tables.items():
                self._create_temp_table(connection, table, rows)
            rows = self._execute_query(connection, normalized_sql, normalized_params)
        return QueryResult(rows=rows, row_count=len(rows), elapsed_ms=int((time.time() - started) * 1000))

    def _create_temp_table(self, connection: Any, table: str, rows: list[dict[str, Any]]) -> None:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
            raise ValueError(f"invalid temporary table name: {table}")
        if not rows:
            raise ValueError(f"cannot materialize empty prior result: {table}")

        columns: list[str] = []
        for row in rows:
            for column in row:
                if column not in columns:
                    columns.append(column)
        if not columns:
            raise ValueError(f"prior result has no columns: {table}")

        quote = connection.dialect.identifier_preparer.quote
        definitions = ", ".join(
            f"{quote(column)} {self._database_type(connection, rows, column)}" for column in columns
        )
        quoted_table = quote(table)
        connection.execute(text(f"DROP TABLE IF EXISTS {quoted_table}"))
        temporary_sql = f"CREATE TEMPORARY TABLE {quoted_table} ({definitions})"
        if connection.dialect.name != "sqlite":
            temporary_sql += " ON COMMIT DROP"
        connection.execute(text(temporary_sql))

        placeholders = ", ".join(f":v_{index}" for index in range(len(columns)))
        insert_sql = text(
            f"INSERT INTO {quoted_table} ({', '.join(quote(column) for column in columns)}) "
            f"VALUES ({placeholders})"
        )
        for row in rows:
            values = {
                f"v_{index}": self._database_value(row.get(column))
                for index, column in enumerate(columns)
            }
            connection.execute(insert_sql, values)

    @staticmethod
    def _database_value(value: Any) -> Any:
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return value

    @staticmethod
    def _database_type(connection: Any, rows: list[dict[str, Any]], column: str) -> str:
        value = next((row.get(column) for row in rows if row.get(column) is not None), None)
        if isinstance(value, bool):
            return "BOOLEAN"
        if isinstance(value, int):
            return "BIGINT"
        if isinstance(value, float):
            return "NUMERIC"
        if isinstance(value, (dict, list)):
            return "JSON" if connection.dialect.name == "sqlite" else "JSONB"
        return "TEXT"
