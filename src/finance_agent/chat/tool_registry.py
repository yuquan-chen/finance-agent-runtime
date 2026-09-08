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
        tool = skill.tool
        if tool.exposure != "direct":
            continue
        name = skill.tool_name()
        description = tool.description or skill.description or skill.title or name
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": tool.input_schema,
                    "strict": tool.strict,
                },
            }
        )
    return tools
