import asyncio
import re
import time
from typing import Any

from finance_agent.llm.provider import LlmProvider


SYSTEM_PROMPT = """你是一个友好的数据分析助手。根据系统数据，用自然、口语化的中文回复用户。

【当前日期】{today}

说话风格：
- 像朋友聊天一样自然，不要太正式
- 用"我"而不是"系统"
- 简洁明了，不要啰嗦

关于 SQL 的解读：
- 【强制】如果系统提供了 SQL，必须使用系统提供的 SQL，不要自己生成新的 SQL！
- SQL 必须放在 ```sql 代码块中；不要在普通文字中重复或改写 SQL。
- 展示 SQL 后，用一句话简单说明这个查询会做什么
- 用通俗的语言解释，比如"按 status 分组，统计每个状态有多少笔交易"
- 不要说"分析思路"、"可以发现什么"这种话，直接说查询做了什么

关于 Python 代码的解读：
- 展示代码后，用一句话简单说明这个函数会做什么
- 用通俗的语言解释，比如"这个函数会取出所有金额，然后计算均值和方差"
- 不要说"分析思路"、"可以发现什么"这种话，直接说代码做了什么

关于上下文：
- 系统会提供【之前的查询记录】，这是用户之前做过的查询
- 理解用户意图时，要结合之前的查询记录
- 当用户说"排序一下"、"筛选一下"、"按XX分组"等操作性指令时，结合正确的历史查询目标和参数化 SQL 重新生成查询
- 后续查询默认按当前最新数据重新执行，不直接读取或计算上一次结果

关于结果展示：
- 【强制】如果查询结果为空，必须说"查询结果为空"，不能编造数据
- 【强制】不能编造任何数据！必须使用系统提供的实际查询结果

必须做的事：
- 如果有 SQL 或 Python 代码，一定要展示给用户看
- 用一句话解释 SQL 或代码做了什么
- 如果需要确认，友好地问用户

不要做的事：
- 不要用"计算方法已准备好"这种机械的话
- 不要用"涉及字段：xxx"这种列表格式
- 不要说"分析思路"、"可以发现什么"这种话
- 【绝对不要】自己生成新的 SQL，必须使用系统提供的 SQL
- 【绝对不能】编造查询结果！如果没有数据就说没有"""


SUMMARIZE_PROMPT = """请总结以下对话历史，提取关键信息。

要求：
1. 只保留用户的核心需求和偏好
2. 只保留关键的查询结果（表名、字段、行数）
3. 不要保留对话细节，只保留结论
4. 用简洁的中文，每条一行
5. 如果没有值得保留的信息，返回空字符串

输出格式：
- 用户查询过 XXX
- 用户偏好 XXX
- 上次查询返回了 N 条记录

示例：
- 用户查询过 Company 5 的 KYC 状态
- 用户偏好按金额降序排列结果
- 上次查询涉及 account 和 cdd_kyc 表"""


async def summarize_conversation(
    conversation_history: list[dict[str, str]],
    llm: LlmProvider,
) -> str:
    """
    总结对话历史，提取关键信息。

    Args:
        conversation_history: 对话历史列表
        llm: LLM 客户端

    Returns:
        总结后的文本
    """
    if not conversation_history:
        return ""

    # 构建对话文本
    conversation_text = ""
    for turn in conversation_history[-10:]:  # 只总结最近 10 轮
        role = "用户" if turn["role"] == "user" else "AI"
        content = turn["content"][:200] + "..." if len(turn["content"]) > 200 else turn["content"]
        conversation_text += f"{role}: {content}\n"

    messages = [
        {"role": "system", "content": SUMMARIZE_PROMPT},
        {"role": "user", "content": f"请总结以下对话历史：\n\n{conversation_text}"},
    ]

    try:
        response = await asyncio.to_thread(
            llm.chat,
            messages,
            temperature=0,
            max_tokens=200,
        )
        return response.content.strip()
    except Exception:
        # 如果总结失败，返回简化版本
        return _fallback_summary(conversation_history)


def _fallback_summary(conversation_history: list[dict[str, str]]) -> str:
    """备用的简化总结（不调用 LLM）。"""
    if not conversation_history:
        return ""

    # 提取用户消息中的关键词
    user_queries = [
        turn["content"][:50]
        for turn in conversation_history
        if turn["role"] == "user"
    ]

    if not user_queries:
        return ""

    return f"- 用户最近查询过：{', '.join(user_queries[-3:])}"


async def generate_reply(
    context: dict[str, Any],
    user_query: str,
    llm: LlmProvider,
    messages: list[dict[str, Any]] | None = None,
) -> str:
    """
    根据结构化上下文生成用户可见的回复。

    Args:
        context: 结构化数据，包含 type, steps, fields, results 等
        user_query: 用户的原始问题
        llm: LLM 客户端
        messages: 对话历史消息列表（LangGraph MessagesState）

    Returns:
        LLM 生成的自然语言回复
    """
    context_text = _format_context(context)

    user_message = f"""用户问题：{user_query}

系统数据：
{context_text}

请根据以上数据生成回复。"""

    # 注入当前日期到系统提示词
    today = time.strftime("%Y-%m-%d")
    system_prompt = SYSTEM_PROMPT.format(today=today)

    # 构建 LLM 调用的 messages，包含对话历史
    llm_messages = [{"role": "system", "content": system_prompt}]

    # 添加对话历史（LangGraph MessagesState 自动管理）
    if messages:
        for msg in messages[-10:]:  # 最近 10 条消息
            if hasattr(msg, 'type') and hasattr(msg, 'content'):
                # LangChain 消息对象
                role = "user" if msg.type == "human" else "assistant"
                llm_messages.append({"role": role, "content": msg.content})
            elif isinstance(msg, dict) and 'role' in msg:
                # 字典格式
                llm_messages.append(msg)

    # 添加当前用户消息
    llm_messages.append({"role": "user", "content": user_message})

    # 使用 asyncio.to_thread 包装同步的 chat 方法
    response = await asyncio.to_thread(
        llm.chat,
        llm_messages,
        temperature=0.7,
    )
    # SQL 只能来自结构化方法，不能由回复 LLM 重新改写。
    # 回复模型仍然负责自然语言解释，但代码块会在返回前同步到唯一事实源。
    return _synchronize_review_sql(response.content.strip(), context)


_CODE_FENCE_RE = re.compile(
    r"```(?P<language>[A-Za-z0-9_+.-]*)?[ \t]*\r?\n(?P<body>[\s\S]*?)```",
    re.IGNORECASE,
)


def _review_sql_templates(context: dict[str, Any]) -> list[str]:
    """取出待确认方法中的规范 SQL；只处理方法审查阶段。"""
    context_type = context.get("type")
    if context_type == "method_review":
        sql = context.get("sql_template")
        return [sql.strip() for sql in [sql] if isinstance(sql, str) and sql.strip()]
    if context_type == "method_set_review":
        templates: list[str] = []
        for step in context.get("steps") or []:
            sql = step.get("sql_template") if isinstance(step, dict) else None
            if isinstance(sql, str) and sql.strip():
                templates.append(sql.strip())
        return templates
    return []


def _looks_like_sql(language: str, body: str) -> bool:
    if language.strip().lower() in {"sql", "postgres", "postgresql", "pgsql"}:
        return True
    # 回复模型有时省略 ```sql 语言标记；只把明显的 SQL 代码块纳入同步。
    if language.strip():
        return False
    return bool(re.match(r"^\s*(?:select|with)\b", body, re.IGNORECASE))


def _synchronize_review_sql(answer: str, context: dict[str, Any]) -> str:
    """用方法 SQL 替换回复中的 SQL 代码块，保证展示与执行完全一致。

    方法审查阶段的 SQL 是参数化模板，不能让普通回复 LLM 重新生成。
    如果模型漏掉代码块，则补到回复末尾；如果多生成了 SQL 代码块，则移除多余块。
    非 SQL 代码（例如 Python）保持原样。
    """
    templates = _review_sql_templates(context)
    if not templates or not answer:
        return answer

    sql_index = 0
    replacements: list[tuple[int, int, str]] = []
    for match in _CODE_FENCE_RE.finditer(answer):
        language = match.group("language") or ""
        body = match.group("body") or ""
        if not _looks_like_sql(language, body):
            continue
        if sql_index < len(templates):
            replacement = f"```sql\n{templates[sql_index]}\n```"
            sql_index += 1
        else:
            # 多余的 SQL 是回复模型自行添加的，不能让它进入用户可见回复。
            replacement = ""
        replacements.append((match.start(), match.end(), replacement))

    if replacements:
        chunks: list[str] = []
        cursor = 0
        for start, end, replacement in replacements:
            chunks.append(answer[cursor:start])
            chunks.append(replacement)
            cursor = end
        chunks.append(answer[cursor:])
        synchronized = "".join(chunks).strip()
    else:
        synchronized = answer.strip()

    if sql_index < len(templates):
        missing = templates[sql_index:]
        if len(templates) == 1:
            label = "系统生成的 SQL："
            blocks = [f"{label}\n```sql\n{sql}\n```" for sql in missing]
        else:
            blocks = [
                f"步骤 {sql_index + offset + 1} SQL：\n```sql\n{sql}\n```"
                for offset, sql in enumerate(missing)
            ]
        synchronized = f"{synchronized}\n\n" + "\n\n".join(blocks)

    return synchronized.strip()


def _format_context(context: dict[str, Any]) -> str:
    """将结构化数据格式化为自然语言描述，供 LLM 参考"""
    parts = []

    # 根据阶段添加提示
    context_type = context.get("type", "")
    if context_type == "method_review":
        parts.append("【阶段：方法+数据确认】这是展示查询的阶段。请：")
        parts.append("1. 展示 SQL 并简要说明查询会做什么")
        parts.append("2. 说明会查询哪些字段和涉及的人/业务")
        parts.append("3. 问用户是否确认执行（确认后会直接执行查询）")
    elif context_type == "execution_result":
        parts.append("【阶段：执行结果】查询已执行完成，请简要总结结果。")
    elif context_type == "analysis_plan":
        parts.append("【阶段：分析计划】请向用户展示分析计划，确认是否继续。")

    # 注入之前的查询信息（如果有）
    if "prior_queries" in context and context["prior_queries"]:
        parts.append("\n【之前的查询记录】")
        for i, pq in enumerate(context["prior_queries"][-3:], 1):  # 只显示最近3条
            parts.append(f"{i}. 用户问: {pq.get('user_query', '未知')}")
            if pq.get('tables'):
                parts.append(f"   涉及的表: {pq.get('tables')}")
            if pq.get('fields'):
                parts.append(f"   涉及的字段: {pq.get('fields')}")
            parts.append(f"   结果: {pq.get('result_summary', '无')}")

    if "goal" in context:
        parts.append(f"用户想做：{context['goal']}")

    if "steps" in context:
        for i, s in enumerate(context["steps"], 1):
            if s.get("title"):
                parts.append(f"\n步骤{i}：{s['title']}")
            if s.get("goal"):
                parts.append(f"  目的：{s['goal']}")
            if s.get("sql_template"):
                parts.append(f"  SQL：{s['sql_template']}")
            if s.get("code"):
                parts.append(f"  Python 代码：\n{s['code']}")

    if "sql_template" in context:
        parts.append(f"\n要执行的 SQL：\n{context['sql_template']}")

    if "code" in context:
        parts.append(f"\n要执行的 Python 代码：\n{context['code']}")

    if "method_name" in context:
        parts.append(f"方法名：{context['method_name']}")

    if "method_type" in context:
        parts.append(f"方法类型：{context['method_type']}")

    if "fields" in context:
        parts.append(f"用到的字段：{', '.join(context['fields'][:10])}")

    if "tables" in context:
        parts.append(f"涉及的表：{', '.join(context['tables'])}")

    if "requires_authorization" in context and context["requires_authorization"]:
        parts.append("\n注意：用户确认后会直接执行查询")

    # 注入查询结果（execution_result 阶段）
    if "result" in context:
        result = context["result"]
        if isinstance(result, list):
            if len(result) == 0:
                parts.append("\n【查询结果：为空，没有匹配的数据】")
            else:
                parts.append(f"\n【查询结果数据（共 {len(result)} 行，必须基于此数据回复，不能编造）】：")
                for i, row in enumerate(result[:10], 1):
                    parts.append(f"  {i}. {row}")
                if len(result) > 10:
                    parts.append(f"  ... 还有 {len(result) - 10} 行")
        elif isinstance(result, dict):
            parts.append(f"\n【查询结果数据（必须基于此数据回复，不能编造）】：{result}")

    if "error" in context:
        parts.append(f"出错了：{context['error']}")

    return "\n".join(parts)
