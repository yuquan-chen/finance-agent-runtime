from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import create_engine, text

from finance_agent.builder.sql_builder import assert_readonly_sql
from finance_agent.metadata.policy import Policy


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

    def execute(self, sql: str, plan: Any | None = None) -> QueryResult:
        if self.engine is None:
            raise RuntimeError("DATABASE_URL is not configured")
        assert_readonly_sql(sql, self.policy)
        started = time.time()
        with self.engine.connect() as connection:
            dialect = connection.dialect.name
            if dialect == "postgresql":
                connection.execute(text(f"SET LOCAL statement_timeout = {int(self.policy.statement_timeout_ms)}"))
            result = connection.execute(text(sql))
            rows = [dict(row._mapping) for row in result.fetchmany(self.policy.max_rows)]
        return QueryResult(rows=rows, row_count=len(rows), elapsed_ms=int((time.time() - started) * 1000))
