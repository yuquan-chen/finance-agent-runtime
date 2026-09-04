"""Build model-visible tools from the registered business skills.

The registry is the extension point.  Runtime concerns such as authorization,
auditing, approval, and execution are deliberately not exposed as tools.
"""
from __future__ import annotations

from typing import Any

from finance_agent.skills.registry import SkillRegistry


def build_skill_tools(skill_registry: SkillRegistry | None) -> list[dict[str, Any]]:
    """Return OpenAI-compatible function definitions for registered skills."""
    if skill_registry is None:
        return []

    tools: list[dict[str, Any]] = []
    for skill in skill_registry.skills:
        name = skill.entrypoint or skill.name
        description_parts = [
            part.strip()
            for part in (
                skill.title,
                skill.description,
                f"能力类型：{skill.kind}",
                f"适用场景：{'；'.join(skill.when_to_use)}" if skill.when_to_use else "",
            )
            if isinstance(part, str) and part.strip()
        ]
        description = ". ".join(description_parts)
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description or name,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "goal": {
                                "type": "string",
                                "description": "用户希望完成的业务目标，不要生成 SQL。",
                            },
                            "params": {
                                "type": "object",
                                "description": "用户明确提供的筛选值；没有筛选值时传空对象。",
                                "additionalProperties": True,
                            },
                        },
                        "required": ["goal"],
                        "additionalProperties": False,
                    },
                },
            }
        )
    return tools
