from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class Intent(str, Enum):
    latest_by_group = "latest_by_group"
    top_n = "top_n"
    count_distinct = "count_distinct"
    aggregate_by_group = "aggregate_by_group"


class Filter(BaseModel):
    field: str
    op: Literal["=", "!=", "in", ">=", "<=", ">", "<", "between"]
    value: Any


class Metric(BaseModel):
    field: str
    op: Literal["sum", "count", "avg", "min", "max"] = "sum"
    alias: str | None = None


class OrderBy(BaseModel):
    field: str
    direction: Literal["asc", "desc"] = "desc"


class QueryPlan(BaseModel):
    intent: Intent
    table: str
    group_by: str | None = None
    metrics: list[Metric] = Field(default_factory=list)
    filters: list[Filter] = Field(default_factory=list)
    order_by: list[OrderBy] = Field(default_factory=list)
    limit: int = 50
    rationale: str = ""

    @field_validator("limit")
    @classmethod
    def limit_must_be_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("limit must be positive")
        return value
