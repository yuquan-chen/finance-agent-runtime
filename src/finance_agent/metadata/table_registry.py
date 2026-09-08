"""数据库表 Schema 注册表（装饰器 + 自动发现）。

使用 @register_table 和 @register_column 装饰器注册表结构和业务元数据。
从 versioned `schema_catalog/tables/` 目录加载表定义。

用法：
    @register_table(name="card_transaction", description="卡交易记录")
    class CardTransaction:
        @register_column(type="uuid", nullable=False, foreign_key="account.id")
        account_id: str

        @register_column(type="varchar", nullable=True, description="交易状态")
        status: str
"""
from __future__ import annotations

import importlib.util
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field
import yaml


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
DESCRIPTION_OVERLAY_PATH = PROJECT_ROOT / "schema_catalog" / "table_descriptions.yaml"
VALUE_ALIASES_OVERLAY_PATH = PROJECT_ROOT / "schema_catalog" / "value_aliases.yaml"
SCHEMA_TABLES_PATH = PROJECT_ROOT / "schema_catalog" / "tables"


def _load_description_overlay(path: Path = DESCRIPTION_OVERLAY_PATH) -> dict[str, str]:
    """读取不属于 ORM 的业务说明覆盖层。"""
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    tables = raw.get("tables", {}) if isinstance(raw, dict) else {}
    if not isinstance(tables, dict):
        return {}
    return {
        str(table_name): str(description).strip()
        for table_name, description in tables.items()
        if str(description).strip()
    }


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

def _discover_tables() -> None:
    """加载 versioned schema catalog 中的表定义，触发注册装饰器。"""
    if not SCHEMA_TABLES_PATH.is_dir():
        raise RuntimeError(f"schema catalog directory does not exist: {SCHEMA_TABLES_PATH}")

    for table_path in sorted(SCHEMA_TABLES_PATH.glob("*.py")):
        if table_path.name == "__init__.py":
            continue
        module_name = f"finance_agent_schema_catalog.{table_path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, table_path)
        if not spec or not spec.loader:
            raise RuntimeError(f"unable to load schema table definition: {table_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)


@lru_cache(maxsize=1)
def get_default_table_registry() -> TableRegistry:
    """返回预注册所有表的注册表。"""
    _discover_tables()

    registry = TableRegistry()

    description_overlay = _load_description_overlay()
    value_aliases_overlay = _load_value_aliases_overlay()
    for table_data in _pending_tables:
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
                    value_aliases_overlay.get(table_data["name"], {}).get(col["name"], {}).get("semantic_aliases", [])
                    or col.get("semantic_aliases", [])
                ),
                value_aliases=(
                    value_aliases_overlay.get(table_data["name"], {}).get(col["name"], {}).get("value_aliases", {})
                    or col.get("value_aliases", {})
                ),
            )
            for col in table_data["columns"]
        ]
        registry.register(TableMeta(
            name=table_data["name"],
            description=description_overlay.get(table_data["name"], table_data["description"]),
            columns=columns,
            source="decorator",
        ))

    return registry
