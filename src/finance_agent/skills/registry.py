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
    aliases: list[str] | None = None,
    entrypoint: str = "",
    workflow: list[str] | None = None,
    kind: str = "query",
    attachment_behavior: str = "",
    side_agent_handler: str = "",
    card: dict[str, Any] | None = None,
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
            "aliases": aliases or [],
            "entrypoint": entrypoint,
            "workflow": workflow or [],
            "kind": kind,
            "attachment_behavior": attachment_behavior,
            "side_agent_handler": side_agent_handler,
            "card": card or {},
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
    aliases: list[str] = Field(default_factory=list)
    entrypoint: str = ""
    workflow: list[str] = Field(default_factory=list)
    kind: str = "query"
    attachment_behavior: str = ""
    side_agent_handler: str = ""
    card: dict[str, Any] = Field(default_factory=dict)

    def manifest_entry(self) -> dict[str, Any]:
        """精简索引：暴露路由所需元数据，不展开工作流卡片。"""
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "aliases": self.aliases,
            "entrypoint": self.entrypoint or self.name,
            "kind": self.kind,
            "card_type": self.card.get("type") if isinstance(self.card, dict) else None,
            "when_to_use": self.when_to_use,
            "attachment_behavior": self.attachment_behavior,
            "side_agent_handler": self.side_agent_handler or "general",
        }

    def detail_spec(self) -> dict[str, Any]:
        return {
            "skill_id": self.name,
            "title": self.title,
            "description": self.description,
            "when_to_use": self.when_to_use,
            "suggested_capabilities": self.suggested_capabilities,
            "required_metadata_terms": self.required_metadata_terms,
            "clarification_policy": self.clarification_policy,
            "risk_notes": self.risk_notes,
            "aliases": self.aliases,
            "entrypoint": self.entrypoint or self.name,
            "workflow": self.workflow,
            "kind": self.kind,
            "attachment_behavior": self.attachment_behavior,
            "side_agent_handler": self.side_agent_handler or "general",
            "card": self.card,
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

    def resolve(self, name_or_alias: str) -> SkillSpec | None:
        """Resolve a canonical Skill name or a configured alias."""
        normalized = name_or_alias.casefold()
        return next(
            (
                skill
                for skill in self.skills
                if skill.name.casefold() == normalized
                or (skill.entrypoint and skill.entrypoint.casefold() == normalized)
                or any(alias.casefold() == normalized for alias in skill.aliases)
            ),
            None,
        )

    def manifest_for_llm(self) -> list[dict[str, Any]]:
        return [skill.manifest_entry() for skill in self.skills]

    def detail_for_skill(self, name: str) -> dict[str, Any] | None:
        skill = self.get(name)
        return skill.detail_spec() if skill else None


def load_skill_registry(path: Path) -> SkillRegistry:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    registry = SkillRegistry.model_validate(raw)

    # 合并装饰器注册的技能（不覆盖 YAML 中已有的）
    existing_names = registry.names()
    for skill in _pending_skills:
        if skill["name"] not in existing_names:
            registry.skills.append(SkillSpec(**skill))

    return registry
