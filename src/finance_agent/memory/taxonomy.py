"""Memory 分类定义。

参考 Claude Code 的 4 类 taxonomy：
- user: 用户是谁
- feedback: 以后怎么做
- project: 项目当前语境
- reference: 去哪找信息
"""
from __future__ import annotations

from enum import Enum


class MemoryType(str, Enum):
    """Memory 类型枚举。"""

    USER = "user"
    FEEDBACK = "feedback"
    PROJECT = "project"
    REFERENCE = "reference"


# 类型描述（用于 LLM 理解）
MEMORY_TYPE_DESCRIPTIONS: dict[MemoryType, dict[str, str]] = {
    MemoryType.USER: {
        "name": "user",
        "description": "用户画像：角色、偏好、知识水平。用于个性化回复风格和解释粒度。",
        "when_to_save": "了解到用户的角色、偏好、职责或知识水平时",
        "how_to_use": "根据用户画像调整回复风格和详细程度",
        "example": "用户偏好中文回复、不喜欢硬编码回复、是金融分析师",
    },
    MemoryType.FEEDBACK: {
        "name": "feedback",
        "description": "行为约束：用户给出的工作指导，包括正反馈和负反馈。",
        "when_to_save": "用户纠正你的做法，或确认某个非显而易见的方法可行时",
        "how_to_use": "让这些记忆指导你的行为，避免重复同样的错误",
        "example": "SQL 要用参数化、不要全量加载 memory、先确认再执行",
    },
    MemoryType.PROJECT: {
        "name": "project",
        "description": "项目上下文：无法从代码直接推导的信息，如截止日期、业务背景、合规原因。",
        "when_to_save": "了解到项目的业务背景、合规要求、重构原因等",
        "how_to_use": "理解用户请求背后的深层含义",
        "example": "KYC 流程需要审批、沙箱模式不连接真实数据库",
    },
    MemoryType.REFERENCE: {
        "name": "reference",
        "description": "外部引用：指向外部系统中信息的位置。",
        "when_to_save": "了解到外部资源及其用途时",
        "how_to_use": "当用户提到外部系统时，知道去哪找信息",
        "example": "API 文档在 docs/api.md、数据库 schema 在 config/catalog.yaml",
    },
}


def get_type_prompt() -> str:
    """获取类型描述的 prompt 片段。"""
    lines = ["## Memory 类型\n"]
    for desc in MEMORY_TYPE_DESCRIPTIONS.values():
        lines.append(f"### {desc['name']}")
        lines.append(f"- 描述: {desc['description']}")
        lines.append(f"- 何时保存: {desc['when_to_save']}")
        lines.append(f"- 如何使用: {desc['how_to_use']}")
        lines.append(f"- 示例: {desc['example']}")
        lines.append("")
    return "\n".join(lines)
