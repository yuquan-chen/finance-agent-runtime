from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from finance_agent.config import Settings
from finance_agent.llm.provider import LlmProvider
from finance_agent.llm.provider import LlmToolCall
from finance_agent.metadata.business_registry import BusinessTermRegistry
from finance_agent.operations.handler_registry import OperationHandlerRegistry
from finance_agent.operations.registry import OperationRegistry
from finance_agent.skills.registry import SkillRegistry
from finance_agent.chat.tool_registry import build_skill_tools


# ---------------------------------------------------------------------------
# 核心类型
# ---------------------------------------------------------------------------


class MethodProposal(BaseModel):
    """统一的方法提案。有提案 = 需要计算，无提案 = 纯文本回复。"""
    entity_id: str | None = None            # 注册的 capability/skill id
    entity_type: str | None = None          # "capability" | "skill" | None（临时方法）
    # 兼容旧客户端字段。当前统一走重新生成查询路径，不允许 LLM 用它路由到旧结果。
    result_refs: list[str] = Field(default_factory=list)
    # 当前会话安全查询卡的候选编号（1=最新）。不是 result_ref，也不直接代表结果数据。
    base_query_candidate: int | None = None
    goal: str = ""                          # 分析目标
    preferred_runtime: str = "auto"         # sql | python | auto
    reason: str = ""
    # 只保存业务概念，用于后端受控 Schema 搜索；不得包含客户名、金额等筛选值。
    schema_search_terms: list[str] = Field(default_factory=list)
    sql: str | None = None                  # LLM 自写的 SQL（当通用操作不覆盖时）
    params: dict[str, Any] = Field(default_factory=dict)  # SQL 参数值，如 {"customer_name": "Company 10"}
    code: str | None = None                 # LLM 自写的 Python 代码


class RouteIntent(BaseModel):
    """LLM 对用户当前意图的结构化判断。"""

    intent: Literal["query", "intake", "checklist", "draft_review", "clarification", "general"] = "general"
    skill_id: str | None = None
    confidence: float = 0.0
    needs_clarification: bool = False
    reason: str = ""


class ResponsePlan(BaseModel):
    """LLM 输出的响应计划。"""
    message: str = ""                       # 给用户看的文本
    intent: RouteIntent | None = None       # 当前消息的 Skill 路由意图
    method_proposal: MethodProposal | None = None  # 有 = 需要计算
    confidence: float = 1.0

    # 向后兼容旧格式
    assistant_message: str = ""
    proposed_actions: list[dict[str, Any]] = Field(default_factory=list)
    reason: str = ""
    status_hint: str = "chat_response"
    safety_flags: list[str] = Field(default_factory=list)
    refused: bool = False

    def model_post_init(self, __context: Any) -> None:
        # 旧格式 → 新格式迁移
        if not self.message and self.assistant_message:
            self.message = self.assistant_message
        if not self.method_proposal and self.proposed_actions:
            action = self.proposed_actions[0]
            action_type = action.get("type", "respond")
            if action_type not in ("respond", "ask_clarification", "refuse"):
                result_refs = list(action.get("result_refs") or [])
                result_ref = action.get("result_ref")
                if result_ref and result_ref not in result_refs:
                    result_refs.insert(0, result_ref)
                self.method_proposal = MethodProposal(
                    entity_id=action.get("capability_id") or action.get("skill_id"),
                    entity_type="skill" if action.get("skill_id") else ("capability" if action.get("capability_id") else None),
                    result_refs=result_refs,
                    goal=action.get("arguments", {}).get("user_goal") or action.get("method_goal") or "",
                    preferred_runtime=action.get("preferred_runtime") or "auto",
                    reason=action.get("reason", ""),
                )


class ResponseValidationResult(BaseModel):
    """系统校验结果。"""
    allowed: bool
    route: Literal["direct_response", "method_flow"]
    proposal: MethodProposal | None = None
    status: str                             # chat / clarification / refusal / proposed
    user_goal: str = ""
    disclosure: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 安全规则
# ---------------------------------------------------------------------------

UNSAFE_PATTERNS = [
    r"\bdrop\b",
    r"\bdelete\b",
    r"\bupdate\b",
    r"\binsert\b",
    r"\btruncate\b",
    "删除数据",
    "修改数据库",
    "绕过权限",
    "导出身份证",
    "导出密码",
    "查看密码",
]

# 真正危险的操作（在 SELECT 语句中会泄露数据或执行危险操作）
DANGEROUS_SELECT_PATTERNS = [
    "INTO OUTFILE",  # 把查询结果写到文件（泄露数据）
    "LOAD_FILE",     # 读取文件内容（泄露数据）
]

# ---------------------------------------------------------------------------
# 分层 Prompt：INSTRUCTIONS（稳定） + CONTEXT（动态） + USER_QUERY
# ---------------------------------------------------------------------------

# Layer 1: Instructions — 稳定，可缓存
INSTRUCTIONS = """# 角色
你是金融数据分析 Agent 的响应规划器。
你只负责决策：用户的问题该走哪条路。
你不执行任何工具，不读取真实数据。

# 输出格式
{
  "message": "给用户看的中文消息",
  "intent": {
    "intent": "query | intake | checklist | draft_review | clarification | general",
    "skill_id": "来自 context.skills 的 id；无法确定时留空",
    "confidence": 0.0,
    "needs_clarification": false,
    "reason": "简短说明"
  },
  "method_proposal": {
    "entity_id": "匹配的能力/技能 id，无匹配留空",
    "entity_type": "capability 或 skill，无匹配留空",
    "result_refs": [],
    "base_query_candidate": null,
    "goal": "不包含用户实际筛选值的分析目标",
    "preferred_runtime": "sql | python | auto",
    "reason": "简短原因",
    "schema_search_terms": ["用于查找表的业务概念，不含用户实际筛选值"],
    "sql": null,
    "params": {}
  },
  "confidence": 0.0
}

# 路由规则（按优先级）

## 0. 模型路由协议
- 如果请求只是说明、能力咨询、帮助或闲聊，直接返回自然语言 message，不调用 Skill。
- 如果请求需要业务能力，优先调用 context.skills 中唯一匹配的 Skill function；tool 参数只包含 goal 和用户明确提供的 params。
- Skill function 只表示业务入口；身份校验、权限、Schema 校验、审计、审批、状态保存和执行均由系统 Runtime 完成，不作为模型工具。
- 不要生成 SQL，也不要调用未出现在 context.skills 中的名称。

## 1. 安全拦截（最高优先级）
以下请求直接拒绝，method_proposal 设为 null，message 说明原因：
- 修改/删除/写入数据库
- 绕过权限、导出敏感信息

## 2. 非分析类 → method_proposal 设为 null
- 问候：hi、你好、hello
- 功能询问：你有什么功能、你能做什么
- 帮助：怎么用、帮助、help
- 闲聊：天气、谢谢

## 3. Skill 意图判定
- intent 必须从 query、intake、checklist、draft_review、clarification、general 中选择。
- query：查询或分析已经存在的业务/客户/KYC 数据，通常选择 kind 为 query 的 Skill。
- intake：填写新的 KYC/身份进件、上传材料、OCR、确认字段，选择对应的 workflow Skill。
- checklist：只查看材料、步骤或要求，选择对应的 knowledge Skill。
- draft_review：检查本地草稿完整性、缺失项或待确认项，选择对应的 workflow Skill。
- 只要用户意图不明确，使用 clarification=true，intent=clarification，method_proposal 设为 null，message 必须提出一个简短澄清问题。
- 上传文件本身不等于 query 或 intake；结合用户文字、当前对话和 Skill 状态判断。没有足够信息时必须澄清。
- skill_id 必须是 context.skills 中已有的 name；不得自行创造 Skill id。

## 4. 数据分析类 → 提出 method_proposal
- 明确请求："统计交易状态"、"Top 10 客户"
- 宽泛分析："业务好不好"、"业务健康度" → 匹配 skill
- 涉及交易/金额/状态/渠道/客户的问题

# 匹配优先级
skill > capability > operations > 新查询

1. 先看 context.skills，description、when_to_use 和 kind 匹配就填 entity_type="skill"
2. 再看 context.capabilities，匹配就填 entity_type="capability"
3. 再看 context.operations，匹配就 entity_id 留空，reason 说明操作名
4. 都不匹配 → entity_id 留空，并把合并后的完整分析目标写入 goal。

# SQL 生成边界
- 你绝不生成 SQL：sql 必须始终为 null。
- 只有后续拿到完整 schema 的查询生成器可以生成 SQL；这样确认卡和执行器只有一个 SQL 来源。
- schema_search_terms 只写 1–5 个业务概念（例如“交易”“状态”“客户”），用于后端搜索受控表目录；
  绝不能填客户名称、账户号、金额、日期等用户实际筛选值，也不能填猜测的表名或字段名。
- 用户补充筛选、字段、时间或排序要求时，结合最近聊天消息，把原需求和新要求合并到 goal。
- 【连续查询强制规则】如果最近一条消息只是补充、修改或指代上一条数据请求（例如“按金额排序”“改成近三个月”“只看失败的”“再加上渠道”），必须继承上一条请求的查询对象、时间范围和筛选条件，生成一条完整的新 goal；不得把它当成新的、信息不足的问题，也不得要求用户重复主体。
- 补充排序/字段/时间时，保留上一条请求中仍然有效的 params；只有用户明确替换筛选值时才替换对应 params。
- 例如：上一条“查询 Company 11 近一年的付款记录”，当前“按金额排序吧” → goal 必须为“查询指定公司近一年的付款记录，并按金额降序排序”，params 仍为 {"customer_name": "Company 11"}。

# 命名参数规则
- params 字段只存储用户提供、将用于筛选的数据值；排序字段、"近一年"这类查询语义不要放入 params。
- goal 必须使用脱值描述，绝不能复述 params 中的实际值。例如用户说"查询 Company 10 的 KYC 状态"，goal 写"查询指定公司的 KYC 状态"。
- 从用户输入中提取参数值，不要写死在 goal 中，更不要写 SQL 中
- 【强制】不要改变参数值的大小写！用户输入什么就保留什么
- 例如用户说"查询 Company 10 的 KYC 状态"，则 params: {"customer_name": "Company 10"}。
- result_refs 必须始终为空；内部结果句柄不属于你的输出。
- 所有后续查询都走“重新生成查询路径”：参考安全的历史 goal/参数化 SQL，重新生成完整 SQL，
  再按当前最新数据执行。不要尝试直接读取或计算上一次结果。
- 如果 context.prior_results 中存在多个历史查询，只有在当前消息明确是后续修改时，
  才填写 base_query_candidate；只能填写 context 中出现的 query_candidate 编号，不能猜编号。
"""

# Layer 2: Context — 纯数据索引，不加任何指导语
def build_context_block(
    capability_manifest: list[dict[str, Any]] | None,
    skill_manifest: list[dict[str, Any]] | None,
    prior_results: list[dict[str, Any]],
    total_prior_count: int,
    handler_manifest: list[dict[str, str]] | None = None,
    business_term_manifest: list[dict[str, Any]] | None = None,
    table_summary: list[dict[str, Any]] | None = None,
    relevant_memories: list[dict[str, Any]] | None = None,
    table_detail_level: str = "full",  # "summary" | "full"
) -> str:
    """构建纯数据 context。指导语全在 INSTRUCTIONS，这里只放索引数据。

    table_detail_level:
        - "summary": 只发送表名和描述（用于路由，~5K tokens）
        - "full": 发送完整的列信息（用于生成 SQL，~39K tokens）
    """
    context: dict[str, Any] = {}

    # 能力索引：只暴露 name + description
    if capability_manifest:
        context["capabilities"] = [
            {"name": c.get("name", c.get("capability_id", "")), "description": c.get("description", "")}
            for c in capability_manifest
        ]

    # 技能索引：只暴露 name + title + description
    if skill_manifest:
        context["skills"] = [
            {"name": s.get("name", s.get("skill_id", "")), "title": s.get("title", ""), "description": s.get("description", "")}
            for s in skill_manifest
        ]

    # 通用操作索引：name + title + description
    if handler_manifest:
        context["operations"] = handler_manifest

    # 业务词典：name + description + aliases
    if business_term_manifest:
        context["business_terms"] = business_term_manifest

    # 表信息：根据 detail_level 控制详细程度
    if table_summary:
        if table_detail_level == "summary":
            # 第一层：只发送表名和描述（用于路由）
            context["table_manifest"] = [
                {"name": t["name"], "description": t.get("description", "")}
                for t in table_summary
            ]
        else:
            # 第二层：发送完整的列信息（用于生成 SQL）
            context["table_manifest"] = table_summary

    # 先前结果索引：只暴露结构信息
    if prior_results:
        context["prior_results"] = {
            "total": total_prior_count,
            "shown": len(prior_results),
            "entries": prior_results,
        }

    # 相关记忆（新系统）
    if relevant_memories:
        context["relevant_memories"] = relevant_memories

    return json.dumps(context, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------


def plan_response_with_llm(message: str, settings: Settings, llm_provider: LlmProvider) -> ResponsePlan:
    return plan_response_with_llm_and_registry(message, settings, llm_provider, None, public_memory_context=[])


def plan_response_with_llm_and_registry(
    message: str,
    settings: Settings,
    llm_provider: LlmProvider,
    operation_registry: OperationRegistry | None,
    skill_registry: SkillRegistry | None = None,
    public_memory_context: list[dict[str, Any]] | None = None,
    sent_memory_count: int = 0,
    handler_registry: OperationHandlerRegistry | None = None,
    business_term_registry: BusinessTermRegistry | None = None,
    table_manifest: list[dict[str, Any]] | None = None,
    relevant_memories: list[dict[str, Any]] | None = None,
    conversation_messages: list[dict[str, Any]] | None = None,
    table_detail_level: str = "summary",  # "summary" | "full"
) -> ResponsePlan:
    safety = hard_safety_plan(message)
    if safety:
        return safety

    # Layer 1: Instructions（稳定，可缓存）
    # Layer 2: Context（动态，每轮更新）
    # Layer 3: User query（纯用户消息）
    all_memory = public_memory_context or []
    new_memory = all_memory[sent_memory_count:]  # 增量：只发新增的 memory
    context_block = build_context_block(
        capability_manifest=operation_registry.manifest_for_llm() if operation_registry else None,
        skill_manifest=skill_registry.manifest_for_llm() if skill_registry else None,
        prior_results=new_memory,
        total_prior_count=len(all_memory),
        handler_manifest=handler_registry.manifest_for_llm() if handler_registry else None,
        business_term_manifest=business_term_registry.manifest_for_llm() if business_term_registry else None,
        table_summary=table_manifest,
        relevant_memories=relevant_memories,
        table_detail_level=table_detail_level,
    )

    # 构建 messages，包含对话历史
    llm_messages = [
        {"role": "system", "content": INSTRUCTIONS},
        {"role": "user", "content": context_block},
    ]

    # 注入对话历史（最近 6 轮）
    if conversation_messages:
        for msg in conversation_messages[-12:]:  # 最近 12 条消息（6 轮对话）
            if hasattr(msg, 'type') and hasattr(msg, 'content'):
                # LangChain 消息对象
                role = "user" if msg.type == "human" else "assistant"
                llm_messages.append({"role": role, "content": msg.content})
            elif isinstance(msg, dict) and 'role' in msg:
                # 字典格式
                llm_messages.append(msg)

    # 添加当前用户消息
    llm_messages.append({"role": "user", "content": message})

    tool_response = _try_model_tool_call(llm_provider, llm_messages, skill_registry)
    if tool_response is not None:
        if tool_response.tool_calls:
            return _plan_from_tool_calls(tool_response.tool_calls, message, skill_registry)
        if tool_response.content.strip():
            return ResponsePlan(message=tool_response.content.strip(), method_proposal=None)

    payload, _ = llm_provider.chat_json(llm_messages, temperature=0)
    plan = _parse_payload(payload, message)
    return _normalize(plan, message)


def _try_model_tool_call(
    llm_provider: LlmProvider,
    messages: list[dict[str, str]],
    skill_registry: SkillRegistry | None,
):
    """Ask a tool-capable provider for a model-selected business capability.

    Providers without ``chat_with_tools`` keep using the legacy structured JSON
    planner.  This keeps the routing contract portable across local models.
    """
    chat_with_tools = getattr(llm_provider, "chat_with_tools", None)
    tools = build_skill_tools(skill_registry)
    if not callable(chat_with_tools) or not tools:
        return None
    try:
        tool_messages = [
            messages[0],
            {
                "role": "system",
                "content": (
                    "本轮使用 function calling 路由协议。不要输出规划 JSON。"
                    "只有用户明确要求查询、统计、计算或分析已有业务数据时，"
                    "才调用一个最匹配的已注册 Skill function。"
                    "如果用户只是在询问系统能做什么、有哪些数据或如何使用，"
                    "直接用普通中文回答，不调用任何 function。"
                    "这类回答只能依据 context 中的已注册能力，保持简洁，不要虚构表名、字段名或未注册的业务类型。"
                    "除非用户要求，否则不要堆叠示例。"
                    "不要因为上下文里出现某个 Skill 就调用它；不要调用与用户目标无关的 Skill。"
                ),
            },
            *messages[1:],
        ]
        return chat_with_tools(tool_messages, tools, temperature=0)
    except Exception:
        # A compatible endpoint may advertise no tool support.  The existing
        # JSON contract is a deliberate compatibility fallback in that case.
        return None


def _plan_from_tool_calls(
    tool_calls: tuple[LlmToolCall, ...],
    message: str,
    skill_registry: SkillRegistry | None,
) -> ResponsePlan:
    """Convert a validated model tool call into the existing query contract."""
    call = tool_calls[0]
    skill = skill_registry.resolve(call.name) if skill_registry else None
    if skill is None:
        return ResponsePlan(
            message="我暂时无法匹配这个业务能力，请换一种方式描述你的需求。",
            method_proposal=None,
            confidence=0.0,
        )
    arguments = call.arguments if isinstance(call.arguments, dict) else {}
    params = arguments.get("params")
    return ResponsePlan(
        message="",
        method_proposal=MethodProposal(
            entity_id=skill.name,
            entity_type="skill",
            goal=str(arguments.get("goal") or message.strip()),
            params=params if isinstance(params, dict) else {},
            reason=f"LLM selected registered skill: {skill.name}",
        ),
        confidence=1.0,
    )


def validate_response_plan(
    plan: ResponsePlan,
    message: str,
    operation_registry: OperationRegistry,
    skill_registry: SkillRegistry | None = None,
) -> ResponseValidationResult:
    """校验 LLM 输出的 ResponsePlan，返回路由决策。"""
    safety = hard_safety_plan(message)
    if safety:
        return ResponseValidationResult(
            allowed=False,
            route="direct_response",
            status="refusal",
            user_goal=message.strip(),
        )

    proposal = plan.method_proposal

    # 无提案 → 直接回复（不走分析流程）。是否需要分析由模型通过
    # tool_call 或兼容的结构化提案表达，Runtime 不根据业务关键词猜测。
    if not proposal:
        return ResponseValidationResult(
            allowed=True,
            route="direct_response",
            status="chat",
            user_goal=message.strip(),
        )

    # 统一走重新生成查询路径：即使旧客户端/模型带了 result_ref，也不能触发
    # “直接读取上一次结果”的历史结果计算路径。历史查询会通过安全的 goal、参数化
    # SQL 和用户消息提供给后续规划器，后端随后重新生成并执行 SQL。
    legacy_refs = list(proposal.result_refs or [])
    proposal.result_refs = []
    if legacy_refs:
        proposal.reason = proposal.reason or "忽略旧结果引用，按当前数据重新生成并执行查询"

    validation = _validate_proposal(proposal, message, operation_registry, skill_registry)
    if legacy_refs:
        validation.warnings.append("当前统一采用重新生成查询路径：忽略旧结果引用，按最新数据重新查询")
    return validation


# ---------------------------------------------------------------------------
# 内部函数
# ---------------------------------------------------------------------------


def _validate_proposal(
    proposal: MethodProposal,
    message: str,
    operation_registry: OperationRegistry,
    skill_registry: SkillRegistry | None,
    warnings: list[str] | None = None,
) -> ResponseValidationResult:
    """校验一个 MethodProposal。"""
    user_goal = proposal.goal or message.strip()
    entity_id = proposal.entity_id
    entity_type = proposal.entity_type
    disclosure: dict[str, Any] = {}
    warns = list(warnings or [])

    # LLM 自写 SQL 安全检查
    if proposal.sql:
        sql_upper = proposal.sql.upper()
        # 检查是否以 SELECT 开头（只读查询）
        if not sql_upper.strip().startswith("SELECT"):
            return ResponseValidationResult(
                allowed=False,
                route="direct_response",
                status="refusal",
                user_goal=user_goal,
                errors=["LLM SQL 必须以 SELECT 开头"],
            )
        # 检查真正危险的操作（在 SELECT 语句中会泄露数据或执行危险操作）
        for pattern in DANGEROUS_SELECT_PATTERNS:
            if pattern in sql_upper:
                return ResponseValidationResult(
                    allowed=False,
                    route="direct_response",
                    status="refusal",
                    user_goal=user_goal,
                    errors=[f"LLM SQL 包含危险操作: {pattern}"],
                )

    # 有 entity_id → 查注册表
    if entity_id:
        if entity_type == "skill" or _looks_like_skill(entity_id):
            # 技能校验
            if skill_registry and skill_registry.get(entity_id):
                detail = skill_registry.detail_for_skill(entity_id)
                disclosure = {"mode": "progressive_skill_detail", "entity_id": entity_id, "skill_detail": detail}
                entity_type = "skill"
            else:
                # 技能不存在 → 降级为临时方法
                warns.append(f"技能未注册: {entity_id}，降级为临时方法")
                entity_id = None
                entity_type = None
        else:
            # 能力校验
            if operation_registry.get(entity_id):
                detail = operation_registry.detail_for_capability(entity_id)
                disclosure = {"mode": "progressive_capability_detail", "entity_id": entity_id, "capability_detail": detail}
                entity_type = "capability"
            else:
                # 能力不存在 → 降级为临时方法
                warns.append(f"能力未注册: {entity_id}，降级为临时方法")
                entity_id = None
                entity_type = None

    # 构建最终提案
    final_proposal = MethodProposal(
        entity_id=entity_id,
        entity_type=entity_type,
        # 重新生成查询路径不把内部结果句柄交给后续路由。
        result_refs=[],
        goal=user_goal,
        base_query_candidate=proposal.base_query_candidate,
        preferred_runtime=proposal.preferred_runtime,
        reason=proposal.reason,
        schema_search_terms=_safe_schema_search_terms(proposal.schema_search_terms, proposal.params),
        sql=proposal.sql,
        params=proposal.params,
    )

    # 路由：有 result_refs → result_ref_flow（现在合并到 method_flow）
    status = "proposed"
    if entity_type == "skill":
        status = "skill_proposed"
    elif entity_type == "capability":
        status = "capability_proposed"
    elif not entity_id:
        status = "method_draft_proposed"

    return ResponseValidationResult(
        allowed=True,
        route="method_flow",
        proposal=final_proposal,
        status=status,
        user_goal=user_goal,
        disclosure=disclosure,
        warnings=warns,
    )


def _safe_schema_search_terms(terms: list[str], params: dict[str, Any]) -> list[str]:
    """Schema 搜索词是业务元数据，不得把用户的真实筛选值带到后续模型调用。"""
    private_values = {
        str(value).strip().casefold()
        for value in params.values()
        if isinstance(value, (str, int, float)) and str(value).strip()
    }
    safe: list[str] = []
    for term in terms:
        if not isinstance(term, str):
            continue
        normalized = " ".join(term.split()).strip()
        if not normalized or len(normalized) > 40 or normalized.casefold() in private_values:
            continue
        if normalized not in safe:
            safe.append(normalized)
    return safe[:5]


def _normalize_result_refs(proposal: MethodProposal) -> tuple[list[str], list[str]]:
    """规范化并校验 result_refs，只保留私有结果库的 result_xxx 句柄。"""
    refs: list[str] = []
    invalid: list[str] = []
    for r in proposal.result_refs:
        if r.startswith("memory_"):
            r = r.removeprefix("memory_")
        if not re.fullmatch(r"result_[A-Za-z0-9]+", r):
            if r not in invalid:
                invalid.append(r)
            continue
        if r not in refs:
            refs.append(r)
    return refs, invalid


def _looks_like_skill(entity_id: str) -> bool:
    return "skill" in entity_id or "analysis" in entity_id or "review" in entity_id


def _parse_payload(payload: dict[str, Any], message: str) -> ResponsePlan:
    """解析 LLM 输出，兼容新旧格式。"""
    # 兼容模型将 intent 简写为字符串的情况；正常输出仍使用结构化对象。
    if isinstance(payload.get("intent"), str):
        payload = {
            **payload,
            "intent": {
                "intent": payload["intent"],
                "skill_id": payload.get("skill_id"),
                "confidence": payload.get("confidence", 0.0),
                "needs_clarification": payload.get("needs_clarification", False),
            },
        }
    # 新格式：有 message 和 method_proposal
    if "message" in payload:
        return ResponsePlan.model_validate(payload)
    # 旧格式：有 proposed_actions
    if "proposed_actions" in payload:
        return _migrate_old_format(payload, message)
    # 旧格式：有 response_mode（tool_decision 格式）
    if "response_mode" in payload:
        return _migrate_response_mode_format(payload, message)
    # LLM 返回了 AnalysisPlan 格式（误把 analysis 当 response）
    if "steps" in payload and "mode" in payload:
        return ResponsePlan(
            message="",
            method_proposal=MethodProposal(
                goal=payload.get("goal", message.strip()),
                preferred_runtime="auto",
                reason="LLM 返回了分析计划格式",
            ),
            confidence=0.5,
        )
    # 无法识别的格式
    raise ValueError(f"无法解析 LLM 输出: {list(payload.keys())}")


def _migrate_response_mode_format(payload: dict[str, Any], message: str) -> ResponsePlan:
    """迁移旧的 response_mode 格式。"""
    mode = payload.get("response_mode")
    assistant_message = payload.get("assistant_message") or ""

    if mode == "tool_call":
        tool_args = payload.get("tool_arguments") or {}
        return ResponsePlan(
            message=assistant_message,
            method_proposal=MethodProposal(
                goal=tool_args.get("user_goal") or message.strip(),
                preferred_runtime="auto",
                reason=payload.get("reason", ""),
            ),
            confidence=float(payload.get("confidence") or 1.0),
        )
    return ResponsePlan(
        message=assistant_message,
        method_proposal=None,
        confidence=float(payload.get("confidence") or 1.0),
    )


def _migrate_old_format(payload: dict[str, Any], message: str) -> ResponsePlan:
    """将旧的 proposed_actions 格式迁移为新格式。"""
    actions = payload.get("proposed_actions", [])
    if not actions:
        return ResponsePlan(message=payload.get("assistant_message", ""), confidence=payload.get("confidence", 1.0))

    action = actions[0]
    action_type = action.get("type", "respond")

    if action_type in ("respond", "ask_clarification", "refuse"):
        return ResponsePlan(
            message=payload.get("assistant_message", ""),
            method_proposal=None,
            confidence=payload.get("confidence", 1.0),
        )

    # 有数据分析需求
    result_refs = list(action.get("result_refs") or [])
    result_ref = action.get("result_ref")
    if result_ref and result_ref not in result_refs:
        result_refs.insert(0, result_ref)

    return ResponsePlan(
        message=payload.get("assistant_message", "我会先准备一个安全的分析方法。"),
        method_proposal=MethodProposal(
            entity_id=action.get("capability_id") or action.get("skill_id"),
            entity_type="skill" if action.get("skill_id") else ("capability" if action.get("capability_id") else None),
            result_refs=result_refs,
            goal=action.get("arguments", {}).get("user_goal") or action.get("method_goal") or message.strip(),
            preferred_runtime=action.get("preferred_runtime") or "auto",
            reason=action.get("reason", ""),
        ),
        confidence=payload.get("confidence", 1.0),
    )


def _normalize(plan: ResponsePlan, message: str) -> ResponsePlan:
    """确保计划完整。"""
    if not plan.message:
        plan.message = message or ""
    if plan.intent:
        if plan.intent.intent == "clarification" or plan.intent.needs_clarification:
            plan.method_proposal = None
            plan.status_hint = "clarification"
        elif plan.intent.skill_id and plan.method_proposal is None:
            # 让模型只负责选择 Skill，后端仍会通过注册表校验并决定最终执行路径。
            plan.method_proposal = MethodProposal(
                entity_id=plan.intent.skill_id,
                entity_type="skill",
                goal=message.strip(),
                reason=plan.intent.reason or "按结构化意图选择 Skill",
            )
    return plan


def hard_safety_plan(message: str) -> ResponsePlan | None:
    """硬性安全拦截。"""
    normalized = re.sub(r"\s+", " ", message.strip().lower())
    if any(re.search(pattern, normalized, re.IGNORECASE) for pattern in UNSAFE_PATTERNS):
        return ResponsePlan(
            message="这个请求我不能执行。当前系统只支持只读、安全、可授权的数据分析流程，不会修改数据库或绕过权限。",
            method_proposal=None,
            confidence=1.0,
            refused=True,
            safety_flags=["unsafe_data_operation"],
        )
    return None
