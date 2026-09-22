from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# 装饰器注册（与 YAML 双轨）
# ---------------------------------------------------------------------------

_pending_skills: list[dict[str, Any]] = []


def _default_tool_input_schema() -> dict[str, Any]:
    """Return the smallest useful model-facing contract for a Skill."""
    return {
        "type": "object",
        "properties": {
            "goal": {
                "type": "string",
                "description": "用户希望完成的业务目标。不要生成 SQL 或执行代码。",
            }
        },
        "required": ["goal"],
        "additionalProperties": False,
    }


class SkillToolSpec(BaseModel):
    """The model-facing contract for one registered Skill."""

    name: str = ""
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=_default_tool_input_schema)
    output_schema: dict[str, Any] | None = None
    strict: bool = True
    exposure: Literal["direct", "deferred", "hidden"] = "direct"

    @model_validator(mode="after")
    def validate_input_schema(self) -> SkillToolSpec:
        if self.input_schema.get("type") != "object":
            raise TypeError("Skill tool input_schema must describe an object")
        properties = self.input_schema.get("properties", {})
        if not isinstance(properties, dict):
            raise TypeError("Skill tool input_schema.properties must be an object")
        required = self.input_schema.get("required", [])
        if not isinstance(required, list) or any(name not in properties for name in required):
            raise ValueError("Skill tool input_schema.required must reference properties")
        if self.strict and self.input_schema.get("additionalProperties") is not False:
            raise ValueError("strict Skill tool schemas must set additionalProperties=false")
        return self

    def validate_arguments(self, arguments: dict[str, Any]) -> list[str]:
        """Validate the small JSON boundary before it becomes a runtime proposal."""
        properties = self.input_schema.get("properties", {})
        required = self.input_schema.get("required", [])
        errors = [f"missing required tool argument: {name}" for name in required if name not in arguments]
        if self.input_schema.get("additionalProperties") is False:
            errors.extend(
                f"unknown tool argument: {name}"
                for name in arguments
                if name not in properties
            )
        for name, value in arguments.items():
            definition = properties.get(name)
            if isinstance(definition, dict):
                errors.extend(_validate_schema_value(value, definition, name))
        return errors


class SkillRuntimeSpec(BaseModel):
    """Internal binding for a Skill; never sent to the model as a tool."""

    executor: str = ""
    policy_ref: str = ""
    state_scope: Literal["request", "session", "workspace"] = "session"
    streaming: bool = True


def _matches_json_type(value: Any, expected_type: str | None) -> bool:
    if isinstance(expected_type, list):
        return any(_matches_json_type(value, item) for item in expected_type)
    if expected_type is None:
        return True
    return {
        "string": lambda: isinstance(value, str),
        "object": lambda: isinstance(value, dict),
        "array": lambda: isinstance(value, list),
        "boolean": lambda: isinstance(value, bool),
        "integer": lambda: isinstance(value, int) and not isinstance(value, bool),
        "number": lambda: isinstance(value, (int, float)) and not isinstance(value, bool),
        "null": lambda: value is None,
    }.get(expected_type, lambda: True)()


def _validate_schema_value(value: Any, schema: dict[str, Any], path: str) -> list[str]:
    """Validate the subset of JSON Schema used by model-facing Skill tools."""
    alternatives = schema.get("oneOf") or schema.get("anyOf")
    if isinstance(alternatives, list):
        if any(not _validate_schema_value(value, option, path) for option in alternatives if isinstance(option, dict)):
            return []
        return [f"invalid tool argument type: {path}"]

    expected_type = schema.get("type")
    if not _matches_json_type(value, expected_type):
        return [f"invalid tool argument type: {path}"]
    if "enum" in schema and value not in schema["enum"]:
        return [f"invalid tool argument value: {path}"]
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        errors = [
            f"missing required tool argument: {path}.{name}"
            for name in required
            if name not in value
        ]
        if schema.get("additionalProperties") is False:
            errors.extend(
                f"unknown tool argument: {path}.{name}"
                for name in value
                if name not in properties
            )
        for name, child in value.items():
            if isinstance(properties.get(name), dict):
                errors.extend(_validate_schema_value(child, properties[name], f"{path}.{name}"))
        return errors
    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        return [
            error
            for index, item in enumerate(value)
            for error in _validate_schema_value(item, schema["items"], f"{path}[{index}]")
        ]
    return []


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
    tool: dict[str, Any] | None = None,
    runtime: dict[str, Any] | None = None,
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
            "tool": tool or {},
            "runtime": runtime or {},
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
    tool: SkillToolSpec = Field(default_factory=SkillToolSpec)
    runtime: SkillRuntimeSpec = Field(default_factory=SkillRuntimeSpec)

    def tool_name(self) -> str:
        return self.tool.name or self.entrypoint or self.name

    def manifest_entry(self) -> dict[str, Any]:
        """精简索引：暴露路由所需元数据，不展开工作流卡片。"""
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "aliases": self.aliases,
            "entrypoint": self.entrypoint or self.name,
            "tool_name": self.tool_name(),
            "kind": self.kind,
            "card_type": self.card.get("type") if isinstance(self.card, dict) else None,
            "when_to_use": self.when_to_use,
            "attachment_behavior": self.attachment_behavior,
            "side_agent_handler": self.side_agent_handler or "general",
            "runtime_executor": self.runtime.executor or None,
        }

    def detail_spec(self) -> dict[str, Any]:
        is_query = self.kind == "query"
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
            "tool": self.tool.model_dump(mode="json"),
            "runtime": self.runtime.model_dump(mode="json"),
            "workflow": self.workflow,
            "kind": self.kind,
            "attachment_behavior": self.attachment_behavior,
            "side_agent_handler": self.side_agent_handler or "general",
            "card": self.card,
            "data_access": (
                "metadata_only_until_system_validation"
                if is_query
                else "skill_state_scoped"
            ),
            "authorization_policy": (
                "query_guard_then_execute"
                if is_query
                else "skill_workflow_policy"
            ),
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
