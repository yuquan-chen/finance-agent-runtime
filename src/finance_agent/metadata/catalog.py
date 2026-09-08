from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class ColumnMeta(BaseModel):
    name: str
    type: str
    semantic: str = ""
    sensitive: bool = False
    semantic_aliases: list[str] = Field(default_factory=list)
    value_aliases: dict[str, list[str]] = Field(default_factory=dict)


class RelationshipMeta(BaseModel):
    from_field: str | None = Field(default=None, alias="from")
    to: str | None = None
    type: str | None = None


class TableMeta(BaseModel):
    name: str
    description: str = ""
    primary_key: str | None = None
    allowed_intents: list[str] = Field(default_factory=list)
    columns: list[ColumnMeta] = Field(default_factory=list)
    relationships: list[RelationshipMeta] = Field(default_factory=list)

    @property
    def column_names(self) -> set[str]:
        return {column.name for column in self.columns}

    def get_column(self, name: str) -> ColumnMeta | None:
        return next((column for column in self.columns if column.name == name), None)


class Catalog(BaseModel):
    version: str
    description: str = ""
    tables: list[TableMeta] = Field(default_factory=list)
    business_terms: dict[str, Any] = Field(default_factory=dict)

    def table(self, name: str) -> TableMeta | None:
        return next((table for table in self.tables if table.name == name), None)


def load_catalog(path: Path) -> Catalog:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return Catalog.model_validate(raw)
