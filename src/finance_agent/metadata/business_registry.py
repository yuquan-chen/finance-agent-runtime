"""业务词典装饰器注册系统。

使用 @register_business_term 装饰器自动注册业务术语，
与 catalog.yaml 中的 business_terms 合并。

用法：
    @register_business_term(
        name="消费",
        description="消费类交易，包含购买、刷卡等。",
        aliases=["购买", "刷卡", "purchase"],
        candidate_fields=["type"],
        filters=[{"field": "type", "op": "in", "value": ["consumption", "purchase"]}],
    )
    def _register():
        pass  # 函数体不需要做任何事
"""
from __future__ import annotations

import importlib
import pkgutil
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 业务术语模型
# ---------------------------------------------------------------------------

class BusinessTerm(BaseModel):
    """一个业务术语的定义。"""
    name: str
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    candidate_fields: list[str] = Field(default_factory=list)
    filters: list[dict[str, Any]] = Field(default_factory=list)
    source: str = "decorator"  # "decorator" | "yaml"


# ---------------------------------------------------------------------------
# 全局待注册列表
# ---------------------------------------------------------------------------

_pending_terms: list[dict[str, Any]] = []


def register_business_term(
    *,
    name: str,
    description: str = "",
    aliases: list[str] | None = None,
    candidate_fields: list[str] | None = None,
    filters: list[dict[str, Any]] | None = None,
) -> callable:
    """装饰器：注册一个业务术语。

    用法：
        @register_business_term(
            name="消费",
            description="消费类交易。",
            aliases=["购买", "purchase"],
            candidate_fields=["type"],
            filters=[{"field": "type", "op": "in", "value": ["consumption"]}],
        )
        def _register():
            pass
    """
    def decorator(fn):
        _pending_terms.append({
            "name": name,
            "description": description,
            "aliases": aliases or [],
            "candidate_fields": candidate_fields or [],
            "filters": filters or [],
        })
        return fn
    return decorator


# ---------------------------------------------------------------------------
# 注册表
# ---------------------------------------------------------------------------

class BusinessTermRegistry:
    """业务词典注册表。"""

    def __init__(self) -> None:
        self._terms: dict[str, BusinessTerm] = {}
        self._alias_index: dict[str, str] = {}  # alias → term_name

    def register(self, term: BusinessTerm) -> None:
        self._terms[term.name] = term
        for alias in term.aliases:
            self._alias_index[alias.lower()] = term.name

    def get(self, name: str) -> BusinessTerm | None:
        """按名称或别名查找。"""
        term = self._terms.get(name)
        if term:
            return term
        alias_key = self._alias_index.get(name.lower())
        return self._terms.get(alias_key) if alias_key else None

    def names(self) -> list[str]:
        return list(self._terms.keys())

    def all_terms(self) -> list[BusinessTerm]:
        return list(self._terms.values())

    def manifest_for_llm(self) -> list[dict[str, Any]]:
        """给 LLM 看的精简索引：name + description + aliases。"""
        return [
            {
                "name": t.name,
                "description": t.description,
                "aliases": t.aliases,
            }
            for t in self._terms.values()
        ]

    def to_catalog_dict(self) -> dict[str, Any]:
        """导出为 catalog.yaml 格式的 business_terms 字典。"""
        result = {}
        for term in self._terms.values():
            entry: dict[str, Any] = {"description": term.description}
            if term.candidate_fields:
                entry["candidate_fields"] = term.candidate_fields
            if term.filters:
                entry["filters"] = term.filters
            result[term.name] = entry
        return result


# ---------------------------------------------------------------------------
# 自动发现 + 构建默认注册表
# ---------------------------------------------------------------------------

def _discover_business_terms() -> None:
    """扫描 finance_agent.metadata.business_terms 包，触发装饰器。"""
    try:
        package = importlib.import_module("finance_agent.metadata.business_terms")
    except ModuleNotFoundError:
        return
    for _importer, modname, _ispkg in pkgutil.iter_modules(package.__path__):
        importlib.import_module(f"finance_agent.metadata.business_terms.{modname}")


@lru_cache(maxsize=1)
def get_default_business_registry() -> BusinessTermRegistry:
    """返回预注册所有业务术语的注册表。

    自动扫描装饰器注册 + 合并 catalog.yaml 中的 business_terms。
    """
    _discover_business_terms()

    registry = BusinessTermRegistry()

    # 装饰器注册的术语
    for term_data in _pending_terms:
        registry.register(BusinessTerm(
            name=term_data["name"],
            description=term_data["description"],
            aliases=term_data["aliases"],
            candidate_fields=term_data["candidate_fields"],
            filters=term_data["filters"],
            source="decorator",
        ))

    return registry


def load_business_registry_from_catalog(catalog_business_terms: dict[str, Any]) -> BusinessTermRegistry:
    """从 catalog.yaml 的 business_terms 构建注册表，合并装饰器注册的术语。"""
    _discover_business_terms()

    registry = BusinessTermRegistry()

    # 先加载 YAML 中的术语
    for name, data in catalog_business_terms.items():
        if isinstance(data, dict):
            registry.register(BusinessTerm(
                name=name,
                description=data.get("description", ""),
                aliases=data.get("aliases", []),
                candidate_fields=data.get("candidate_fields", []),
                filters=data.get("filters", []),
                source="yaml",
            ))

    # 再合并装饰器注册的（不覆盖 YAML 已有的）
    existing_names = set(registry.names())
    for term_data in _pending_terms:
        if term_data["name"] not in existing_names:
            registry.register(BusinessTerm(
                name=term_data["name"],
                description=term_data["description"],
                aliases=term_data["aliases"],
                candidate_fields=term_data["candidate_fields"],
                filters=term_data["filters"],
                source="decorator",
            ))

    return registry
