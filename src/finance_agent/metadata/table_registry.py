"""数据库表 Schema 注册表。

Schema 结构从本地 YAML 快照加载；YAML 只包含表、字段、类型和注释，
不包含业务数据。

用法：
    @register_table(name="card_transaction", description="卡交易记录")
    class CardTransaction:
        @register_column(type="uuid", nullable=False, foreign_key="account.id")
        account_id: str

        @register_column(type="varchar", nullable=True, description="交易状态")
        status: str
"""
from __future__ import annotations

import os
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# 列和表模型
# ---------------------------------------------------------------------------

class ColumnMeta(BaseModel):
    """列的元数据。"""
    name: str
    type: str = "text"
    nullable: bool = True
    description: str = ""
    sensitive: bool = False
    foreign_key: str | None = None  # 格式: "table.column"
    enum_values: list[str] = Field(default_factory=list)
    semantic_aliases: list[str] = Field(default_factory=list)
    # canonical value -> user/business aliases, maintained in the schema overlay
    value_aliases: dict[str, list[str]] = Field(default_factory=dict)


class TableMeta(BaseModel):
    """表的元数据。"""
    name: str
    description: str = ""
    columns: list[ColumnMeta] = Field(default_factory=list)
    source: str = "decorator"  # "decorator" | "yaml"

    @property
    def column_names(self) -> set[str]:
        return {col.name for col in self.columns}

    def get_column(self, name: str) -> ColumnMeta | None:
        return next((col for col in self.columns if col.name == name), None)

    def canonical_value(self, column_name: str, value: str) -> str | None:
        """Resolve a configured alias to the column's canonical value."""
        column = self.get_column(column_name)
        if column is None or not column.value_aliases:
            return None
        normalized = "".join(value.casefold().split())
        for canonical, aliases in column.value_aliases.items():
            candidates = [canonical, *aliases]
            if any("".join(candidate.casefold().split()) == normalized for candidate in candidates):
                return canonical
        return None

    def get_relationships(self) -> list[dict[str, str]]:
        """提取外键关系。"""
        rels = []
        for col in self.columns:
            if col.foreign_key:
                rels.append({
                    "from_field": col.name,
                    "to": col.foreign_key,
                    "type": "many_to_one",
                })
        return rels


# ---------------------------------------------------------------------------
# 全局待注册列表
# ---------------------------------------------------------------------------

_pending_tables: list[dict[str, Any]] = []
PROJECT_ROOT = Path(__file__).resolve().parents[3]
VALUE_ALIASES_OVERLAY_PATH = PROJECT_ROOT / "schema_catalog" / "value_aliases.yaml"
SCHEMA_CATALOG_PATH = PROJECT_ROOT / "schema_catalog" / "schema.yaml"


def _load_value_aliases_overlay(path: Path = VALUE_ALIASES_OVERLAY_PATH) -> dict[str, dict[str, dict[str, Any]]]:
    """Load canonical business values without embedding them in runtime code."""
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    tables = raw.get("tables", {}) if isinstance(raw, dict) else {}
    if not isinstance(tables, dict):
        return {}
    result: dict[str, dict[str, dict[str, Any]]] = {}
    for table_name, columns in tables.items():
        if not isinstance(columns, dict):
            continue
        result[str(table_name)] = {}
        for column_name, aliases in columns.items():
            if not isinstance(aliases, dict):
                continue
            values = aliases.get("values", aliases)
            result[str(table_name)][str(column_name)] = {
                "semantic_aliases": [str(alias) for alias in aliases.get("semantic_aliases", [])],
                "value_aliases": {
                    str(canonical): [str(alias) for alias in alias_values if alias is not None]
                    for canonical, alias_values in values.items()
                    if isinstance(alias_values, list) and canonical not in {"semantic_aliases", "values"}
                },
            }
    return result


def register_table(
    *,
    name: str,
    description: str = "",
) -> Callable:
    """装饰器：注册一个数据库表。

    用法：
        @register_table(name="card_transaction", description="卡交易记录")
        class CardTransaction:
            ...
    """
    def decorator(cls: type) -> type:
        columns = []
        # 从类的 COLUMNS 变量中收集列信息
        if hasattr(cls, "COLUMNS") and isinstance(cls.COLUMNS, dict):
            for col_name, col_meta in cls.COLUMNS.items():
                if isinstance(col_meta, dict):
                    col_data = {"name": col_name, **col_meta}
                    columns.append(col_data)

        _pending_tables.append({
            "name": name,
            "description": description,
            "columns": columns,
        })
        return cls
    return decorator


def register_column(
    *,
    col_type: str = "text",
    nullable: bool = True,
    description: str = "",
    sensitive: bool = False,
    foreign_key: str | None = None,
    enum_values: list[str] | None = None,
    original_name: str | None = None,
) -> Callable:
    """装饰器：注册一个列的元数据。

    用法：
        @register_column(col_type="varchar", nullable=True, description="交易状态")
        status: str
    """
    def decorator(fn: Any) -> Any:
        fn._column_meta = {
            "type": col_type,
            "nullable": nullable,
            "description": description,
            "sensitive": sensitive,
            "foreign_key": foreign_key,
            "enum_values": enum_values or [],
            "original_name": original_name,
        }
        return fn
    return decorator


# ---------------------------------------------------------------------------
# 注册表
# ---------------------------------------------------------------------------

class TableRegistry:
    """数据库表 Schema 注册表。"""

    def __init__(self) -> None:
        self._tables: dict[str, TableMeta] = {}

    def register(self, table: TableMeta) -> None:
        self._tables[table.name] = table

    def get(self, name: str) -> TableMeta | None:
        return self._tables.get(name)

    def names(self) -> list[str]:
        return list(self._tables.keys())

    def all_tables(self) -> list[TableMeta]:
        return list(self._tables.values())

    def manifest_for_llm(self) -> list[dict[str, Any]]:
        """给 LLM 看的精简索引：表名 + 描述 + 列名(类型)。"""
        return [
            {
                "name": t.name,
                "description": t.description,
                "columns": [
                    f"{c.name}({c.type})" if not c.description else f"{c.name}({c.type}): {c.description}"
                    for c in t.columns
                ],
                "relationships": t.get_relationships(),
            }
            for t in self._tables.values()
        ]


# ---------------------------------------------------------------------------
# 自动发现 + 构建默认注册表
# ---------------------------------------------------------------------------

def _load_yaml_tables(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise RuntimeError(
            f"schema catalog does not exist: {path}. "
            "Run scripts/extract_schema.py --from-db <DATABASE_URL> first."
        )
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict) or not isinstance(raw.get("tables"), list):
        raise TypeError(f"invalid schema catalog YAML: {path}")
    return [table for table in raw["tables"] if isinstance(table, dict)]


@lru_cache(maxsize=8)
def get_default_table_registry(schema_path: Path | str | None = None) -> TableRegistry:
    """返回从 YAML schema 快照构建的注册表。"""
    path = Path(schema_path or os.environ.get("SCHEMA_CATALOG_PATH", SCHEMA_CATALOG_PATH))
    if (
        not path.exists()
        and path.name == "schema.yaml"
        and os.environ.get("EXECUTOR_MODE", "mock") == "mock"
    ):
        demo_path = path.with_name("demo_schema.yaml")
        if demo_path.exists():
            path = demo_path
    table_data_list = _load_yaml_tables(path)

    registry = TableRegistry()

    value_aliases_overlay = _load_value_aliases_overlay()
    for table_data in table_data_list:
        table_name = str(table_data.get("name") or table_data.get("table_name") or "")
        if not table_name:
            continue
        columns = [
            ColumnMeta(
                name=col["name"],
                type=col.get("type", "text"),
                nullable=col.get("nullable", True),
                description=col.get("description", ""),
                sensitive=col.get("sensitive", False),
                foreign_key=col.get("foreign_key"),
                enum_values=col.get("enum_values", []),
                semantic_aliases=(
                    value_aliases_overlay.get(table_name, {}).get(col["name"], {}).get("semantic_aliases", [])
                    or col.get("semantic_aliases", [])
                ),
                value_aliases=(
                    value_aliases_overlay.get(table_name, {}).get(col["name"], {}).get("value_aliases", {})
                    or col.get("value_aliases", {})
                ),
            )
            for col in table_data.get("columns", [])
            if isinstance(col, dict) and col.get("name")
        ]
        registry.register(TableMeta(
            name=table_name,
            description=table_data.get("description", ""),
            columns=columns,
            source="yaml",
        ))

    return registry
