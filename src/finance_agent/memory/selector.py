"""Memory 选择器。

使用小 LLM 调用选择相关记忆（最多 5 条）。
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from finance_agent.llm.provider import LlmProvider
from finance_agent.memory.memory_store import MemoryFile, MemoryStore

# 选择器系统提示词
SELECTOR_SYSTEM_PROMPT = """你是一个记忆选择器。根据用户的查询，从可用的记忆中选择最相关的记忆。

规则：
1. 只选择与当前查询明确相关的记忆
2. 最多选择 5 条记忆
3. 如果没有相关记忆，返回空列表
4. 优先选择 feedback 和 project 类型的记忆（行为约束和项目上下文）
5. 不确定是否相关时，不要选择

输出格式（JSON）：
{
  "selected": ["memory_name_1", "memory_name_2"],
  "reason": "简短说明为什么选择这些记忆"
}"""


async def select_relevant_memories(
    query: str,
    store: MemoryStore,
    llm: LlmProvider,
    session_id: str,
    max_results: int = 5,
) -> list[MemoryFile]:
    """选择与查询相关的记忆。

    Args:
        query: 用户查询
        store: Memory 存储
        llm: LLM 提供者
        max_results: 最大返回数量

    Returns:
        相关的记忆列表
    """
    # 获取所有记忆
    all_memories = store.list_session_memories(session_id)
    if not all_memories:
        return []

    # 构建 manifest
    manifest = store.get_manifest(limit=50, session_id=session_id)

    # 构建选择器提示词
    messages = [
        {"role": "system", "content": SELECTOR_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"""用户查询：{query}

{manifest}

请从上述记忆中选择与用户查询最相关的记忆（最多 {max_results} 条）。""",
        },
    ]

    try:
        # 使用小 LLM 选择记忆（使用 chat_json 保持一致性）
        result, _ = await asyncio.to_thread(
            llm.chat_json,
            messages,
            temperature=0,
            max_tokens=500,
        )

        # 解析响应
        selected_names = result.get("selected", [])[:max_results]

        # 返回选中的记忆
        selected_memories = []
        for name in selected_names:
            memory = store.get_memory(name)
            if memory and memory.session_id == session_id:
                selected_memories.append(memory)

        return selected_memories

    except Exception as e:
        # 选择失败时返回空列表
        print(f"Memory selection failed: {e}")
        return []


def _parse_response(content: str) -> dict[str, Any]:
    """解析 LLM 响应。"""
    # 尝试直接解析 JSON
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # 尝试从 markdown 代码块中提取 JSON
    import re
    code_block = re.search(r"```(?:json)?\s*(.*?)```", content, re.DOTALL)
    if code_block:
        try:
            return json.loads(code_block.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试提取第一个 JSON 对象
    start = content.find("{")
    end = content.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(content[start:end])
        except json.JSONDecodeError:
            pass

    # 解析失败，返回空
    return {"selected": [], "reason": "Failed to parse response"}


def select_relevant_memories_sync(
    query: str,
    store: MemoryStore,
    llm: LlmProvider,
    session_id: str,
    max_results: int = 5,
) -> list[MemoryFile]:
    """同步版本的记忆选择器。"""
    return asyncio.run(select_relevant_memories(query, store, llm, session_id, max_results))
