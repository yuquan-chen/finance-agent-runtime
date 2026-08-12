from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 装饰器注册（与 YAML 双轨）
# ---------------------------------------------------------------------------

_pending_skills: list[dict[str, Any]] = []


def register_skill(
    *,
    name: str,
    title: str = "",
    description: str = "",
    when_to_use: list[str] | None = None,
    suggested_capabilities: list[str] | None = None,
    required_metadata_terms: list[str] | None = None,
    clarification_policy: str = "",
    risk_notes: list[str] | None = None,
) -> callable:
    """装饰器：注册一个 skill。与 YAML 配置合并。"""
    def decorator(fn):
        _pending_skills.append({
            "name": name,
            "title": title,
            "description": description,
            "when_to_use": when_to_use or [],
            "suggested_capabilities": suggested_capabilities or [],
            "required_metadata_terms": required_metadata_terms or [],
            "clarification_policy": clarification_policy,
            "risk_notes": risk_notes or [],
        })
        return fn
    return decorator


class SkillSpec(BaseModel):
    name: str
    title: str
    description: str = ""
    when_to_use: list[str] = Field(default_factory=list)
    suggested_capabilities: list[str] = Field(default_factory=list)
    required_metadata_terms: list[str] = Field(default_factory=list)
    clarification_policy: str = ""
    risk_notes: list[str] = Field(default_factory=list)

    def manifest_entry(self) -> dict[str, str]:
        """精简索引：只暴露 name + title + description，供 LLM 匹配意图。"""
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
        }

    def detail_spec(self) -> dict[str, str | list[str]]:
        return {
            "skill_id": self.name,
            "title": self.title,
            "description": self.description,
            "when_to_use": self.when_to_use,
            "suggested_capabilities": self.suggested_capabilities,
            "required_metadata_terms": self.required_metadata_terms,
            "clarification_policy": self.clarification_policy,
            "risk_notes": self.risk_notes,
            "data_access": "metadata_only_until_user_authorization",
            "authorization_policy": "method_review_then_execute",
        }


class SkillRegistry(BaseModel):
    version: str
    skills: list[SkillSpec] = Field(default_factory=list)

    def names(self) -> set[str]:
        return {skill.name for skill in self.skills}

    def get(self, name: str) -> SkillSpec | None:
        return next((skill for skill in self.skills if skill.name == name), None)

    def manifest_for_llm(self) -> list[dict[str, str | list[str]]]:
        return [skill.manifest_entry() for skill in self.skills]

    def detail_for_skill(self, name: str) -> dict[str, str | list[str]] | None:
        skill = self.get(name)
        return skill.detail_spec() if skill else None


def load_skill_registry(path: Path) -> SkillRegistry:
    raw = yaml.safe_load(path.read_text()) or {}
    registry = SkillRegistry.model_validate(raw)

    # 合并装饰器注册的技能（不覆盖 YAML 中已有的）
    existing_names = registry.names()
    for skill in _pending_skills:
        if skill["name"] not in existing_names:
            registry.skills.append(SkillSpec(**skill))

    return registry
