from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 装饰器注册（与 YAML 双轨）
# ---------------------------------------------------------------------------

_pending_capabilities: list[dict[str, Any]] = []


def register_capability(
    *,
    name: str,
    description: str = "",
    execution_modes: list[str] | None = None,
    preferred_mode: str = "sql",
    risk_level: str = "low",
    requires_method_review: bool = True,
) -> callable:
    """装饰器：注册一个 capability。与 YAML 配置合并。"""
    def decorator(fn):
        _pending_capabilities.append({
            "name": name,
            "description": description,
            "execution_modes": execution_modes or ["sql"],
            "preferred_mode": preferred_mode,
            "risk_level": risk_level,
            "requires_method_review": requires_method_review,
        })
        return fn
    return decorator


class OperationSpec(BaseModel):
    name: str
    description: str = ""
    execution_modes: list[str] = Field(default_factory=list)
    preferred_mode: str = "sql"
    risk_level: str = "low"
    requires_method_review: bool = True

    def manifest_entry(self) -> dict[str, str]:
        """精简索引：只暴露 name + description，供 LLM 匹配意图。"""
        return {
            "name": self.name,
            "description": self.description,
        }

    def detail_spec(self) -> dict[str, str | bool | list[str]]:
        return {
            "capability_id": self.name,
            "description": self.description,
            "execution_modes": self.execution_modes,
            "preferred_mode": self.preferred_mode,
            "risk_level": self.risk_level,
            "requires_method_review": self.requires_method_review,
            "data_access": "metadata_only_until_user_authorization",
            "authorization_policy": "method_review_then_execute",
        }


class OperationRegistry(BaseModel):
    version: str
    operations: list[OperationSpec] = Field(default_factory=list)

    def names(self) -> set[str]:
        return {operation.name for operation in self.operations}

    def get(self, name: str) -> OperationSpec | None:
        return next((operation for operation in self.operations if operation.name == name), None)

    def manifest_for_llm(self) -> list[dict[str, str]]:
        return [operation.manifest_entry() for operation in self.operations]

    def detail_for_capability(self, name: str) -> dict[str, str | bool | list[str]] | None:
        operation = self.get(name)
        return operation.detail_spec() if operation else None


def load_operation_registry(path: Path) -> OperationRegistry:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    registry = OperationRegistry.model_validate(raw)

    # 合并装饰器注册的能力（不覆盖 YAML 中已有的）
    existing_names = registry.names()
    for cap in _pending_capabilities:
        if cap["name"] not in existing_names:
            registry.operations.append(OperationSpec(**cap))

    return registry
