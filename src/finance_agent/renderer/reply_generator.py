import asyncio
from typing import Any

from finance_agent.llm.provider import LlmProvider


SYSTEM_PROMPT = """你是一个友好的数据分析助手。根据系统数据，用自然、口语化的中文回复用户。

说话风格：
- 像朋友聊天一样自然，不要太正式
- 用"我"而不是"系统"
- 简洁明了，不要啰嗦

关于 SQL 的解读：
- 【强制】如果系统提供了 SQL，必须使用系统提供的 SQL，不要自己生成新的 SQL！
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
- 当用户说"排序一下"、"筛选一下"、"按XX分组"等操作性指令时，是指对之前的查询结果进行操作
- 修改 SQL 时，基于之前的 SQL 进行修改，不要生成全新的查询

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


async def generate_reply(
    context: dict[str, Any],
    user_query: str,
    llm: LlmProvider,
) -> str:
    """
    根据结构化上下文生成用户可见的回复。

    Args:
        context: 结构化数据，包含 type, steps, fields, results 等
        user_query: 用户的原始问题
        llm: LLM 客户端

    Returns:
        LLM 生成的自然语言回复
    """
    context_text = _format_context(context)
    user_message = f"""用户问题：{user_query}

系统数据：
{context_text}

请根据以上数据生成回复。"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    # 使用 asyncio.to_thread 包装同步的 chat 方法
    response = await asyncio.to_thread(
        llm.chat,
        messages,
        temperature=0.7,
    )
    return response.content.strip()


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
