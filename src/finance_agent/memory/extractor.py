"""Memory 提取器。

Turn 结束后，使用 LLM 从对话中提取记忆。
决定更新已有文件 or 创建新文件。
"""
from __future__ import annotations

import asyncio
import re
from typing import Any

from finance_agent.llm.provider import LlmProvider
from finance_agent.memory.memory_store import MemoryFile, MemoryStore
from finance_agent.memory.taxonomy import MemoryType, get_type_prompt

# 提取器系统提示词
EXTRACTOR_SYSTEM_PROMPT = """你是一个记忆提取器。分析用户对话，提取值得长期保存的记忆。

规则：
1. 只提取非显而易见的信息（不能从代码直接推导）
2. 不要提取临时状态、正在进行的工作
3. 不要提取代码模式、架构、文件路径
4. 对于 feedback 类型，必须包含 **Why:** 和 **How to apply:**
5. 每条记忆必须有明确的类型（user/feedback/project/reference）
6. 不要保存账户号、客户名称、金额、日期、证件号、密码、token 或其他原始敏感值

{type_prompt}

输出格式（JSON）：
{{
  "memories": [
    {{
      "name": "memory_name",
      "description": "一行描述",
      "type": "user|feedback|project|reference",
      "content": "记忆内容",
      "action": "create|update"
    }}
  ]
}}

如果没有值得提取的记忆，返回空列表：
{{"memories": []}}"""


async def extract_memories(
    messages: list[dict[str, str]],
    store: MemoryStore,
    llm: LlmProvider,
    session_id: str,
    redact_values: list[Any] | None = None,
) -> list[MemoryFile]:
    """从对话中提取记忆。

    Args:
        messages: 对话消息列表
        store: Memory 存储
        llm: LLM 提供者

    Returns:
        提取的记忆列表
    """
    # 获取现有记忆 manifest
    existing_manifest = store.get_manifest(limit=50, session_id=session_id)

    # 构建提取器提示词
    type_prompt = get_type_prompt()
    system_prompt = EXTRACTOR_SYSTEM_PROMPT.format(type_prompt=type_prompt)

    # 构建对话摘要
    conversation_summary = _summarize_conversation(messages)

    user_message = f"""现有记忆：
{existing_manifest}

最近对话：
{conversation_summary}

请从对话中提取值得长期保存的记忆。"""

    full_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    try:
        # 使用 LLM 提取记忆（使用 chat_json 保持一致性）
        result, _ = await asyncio.to_thread(
            llm.chat_json,
            full_messages,
            temperature=0,
            max_tokens=2000,
        )

        # 解析响应
        memory_updates = result.get("memories", [])

        # 应用更新
        saved_memories = []
        for update in memory_updates:
            memory = _apply_memory_update(update, store, session_id, redact_values=redact_values)
            if memory:
                saved_memories.append(memory)

        return saved_memories

    except Exception as e:  # noqa: BLE001 - memory extraction is best-effort
        print(f"Memory extraction failed: {e}")
        return []


def _summarize_conversation(messages: list[dict[str, str]]) -> str:
    """总结对话内容。"""
    summary_lines = []
    for msg in messages[-10:]:  # 只取最近 10 条
        role = msg.get("role", "unknown")
        content = msg.get("content", "")

        # 截断过长的内容
        if len(content) > 200:
            content = content[:200] + "..."

        summary_lines.append(f"[{role}]: {content}")

    return "\n".join(summary_lines)


def _apply_memory_update(
    update: dict[str, Any],
    store: MemoryStore,
    session_id: str,
    redact_values: list[Any] | None = None,
) -> MemoryFile | None:
    """应用记忆更新。"""
    name = _normalize_memory_name(update.get("name", ""))
    description = _redact_memory_text(update.get("description", ""), redact_values)
    type_str = update.get("type", "project")
    content = _redact_memory_text(update.get("content", ""), redact_values)
    action = update.get("action", "create")

    if not name or not content:
        return None

    prefix = f"session_{session_id[:8]}_"
    if not name.startswith(prefix):
        name = f"{prefix}{name}"

    # 验证类型
    try:
        mem_type = MemoryType(type_str)
    except ValueError:
        mem_type = MemoryType.PROJECT

    # 检查是否已存在
    existing = store.get_memory(name)

    if action == "update" and existing:
        # 更新已有记忆
        existing.description = description or existing.description
        existing.content = content
        existing.type = mem_type
        return store.save_memory(existing)
    else:
        # 创建新记忆
        memory = MemoryFile(
            name=name,
            description=description,
            type=mem_type,
            content=content,
            path=store.base_path / f"{name}.md",
            session_id=session_id,
        )
        return store.save_memory(memory)


def _normalize_memory_name(value: Any) -> str:
    """Restrict model-generated names to safe single-file identifiers."""
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "")).strip("_")
    return name[:80]


def _redact_memory_text(value: Any, redact_values: list[Any] | None) -> str:
    """Remove known request parameter values before storing semantic memory."""
    text = str(value or "")
    for raw_value in sorted(
        (str(item) for item in (redact_values or []) if item is not None),
        key=len,
        reverse=True,
    ):
        if raw_value.strip():
            text = re.sub(re.escape(raw_value), "[参数]", text, flags=re.IGNORECASE)
    return text


async def extract_memories_from_state(
    state: dict[str, Any],
    store: MemoryStore,
    llm: LlmProvider,
) -> list[MemoryFile]:
    """从 AgentState 中提取记忆。

    Args:
        state: AgentState
        store: Memory 存储
        llm: LLM 提供者

    Returns:
        提取的记忆列表
    """
    # 构建消息列表
    messages = []

    # 添加用户查询
    user_query = state.get("user_query", "")
    if user_query:
        messages.append({"role": "user", "content": user_query})

    # 不把 AI 的结果解读放入记忆提取上下文。执行结果可能包含敏感值，
    # 即使它已经展示给用户，也不能因为记忆提取再次进入普通 LLM。
    # 长期记忆只从用户原始请求和错误信息中提取。

    # 添加错误信息（如果有）
    errors = state.get("errors", [])
    if errors:
        messages.append({"role": "system", "content": f"Errors: {', '.join(errors[-3:])}"})

    if not messages:
        return []

    proposal = (state.get("action_validation") or {}).get("proposal") or {}
    redact_values = [
        *(state.get("base_query_params") or {}).values(),
        *(proposal.get("params") or {}).values(),
    ]
    return await extract_memories(
        messages,
        store,
        llm,
        state.get("session_id", ""),
        redact_values=redact_values,
    )


def extract_memories_from_state_sync(
    state: dict[str, Any],
    store: MemoryStore,
    llm: LlmProvider,
) -> list[MemoryFile]:
    """同步版本的记忆提取。"""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 如果事件循环正在运行，使用 run_until_complete
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, extract_memories_from_state(state, store, llm))
                return future.result()
        else:
            return loop.run_until_complete(extract_memories_from_state(state, store, llm))
    except RuntimeError:
        return asyncio.run(extract_memories_from_state(state, store, llm))
