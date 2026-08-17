from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from finance_agent.config import Settings
from finance_agent.llm.provider import LlmProvider
from finance_agent.metadata.business_registry import BusinessTermRegistry
from finance_agent.operations.handler_registry import OperationHandlerRegistry
from finance_agent.operations.registry import OperationRegistry
from finance_agent.skills.registry import SkillRegistry


# ---------------------------------------------------------------------------
# 核心类型
# ---------------------------------------------------------------------------


class MethodProposal(BaseModel):
    """统一的方法提案。有提案 = 需要计算，无提案 = 纯文本回复。"""
    entity_id: str | None = None            # 注册的 capability/skill id
    entity_type: str | None = None          # "capability" | "skill" | None（临时方法）
    # 兼容旧客户端字段。当前统一走 A 路径，不允许 LLM 用它路由到旧结果。
    result_refs: list[str] = Field(default_factory=list)
    # 当前会话安全查询卡的候选编号（1=最新）。不是 result_ref，也不直接代表结果数据。
    base_query_candidate: int | None = None
    goal: str = ""                          # 分析目标
    preferred_runtime: str = "auto"         # sql | python | auto
    reason: str = ""
    sql: str | None = None                  # LLM 自写的 SQL（当通用操作不覆盖时）
    params: dict[str, Any] = Field(default_factory=dict)  # SQL 参数值，如 {"customer_name": "Company 10"}
    code: str | None = None                 # LLM 自写的 Python 代码


class ResponsePlan(BaseModel):
    """LLM 输出的响应计划。"""
    message: str = ""                       # 给用户看的文本
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
  "method_proposal": {
    "entity_id": "匹配的能力/技能 id，无匹配留空",
    "entity_type": "capability 或 skill，无匹配留空",
    "result_refs": [],
    "base_query_candidate": null,
    "goal": "不包含用户实际筛选值的分析目标",
    "preferred_runtime": "sql | python | auto",
    "reason": "简短原因",
    "sql": null,
    "params": {}
  },
  "confidence": 0.0
}

# 路由规则（按优先级）

## 1. 安全拦截（最高优先级）
以下请求直接拒绝，method_proposal 设为 null，message 说明原因：
- 修改/删除/写入数据库
- 绕过权限、导出敏感信息

## 2. 非分析类 → method_proposal 设为 null
- 问候：hi、你好、hello
- 功能询问：你有什么功能、你能做什么
- 帮助：怎么用、帮助、help
- 闲聊：天气、谢谢

## 3. 数据分析类 → 提出 method_proposal
- 明确请求："统计交易状态"、"Top 10 客户"
- 宽泛分析："业务好不好"、"业务健康度" → 匹配 skill
- 涉及交易/金额/状态/渠道/客户的问题

# 匹配优先级
skill > capability > operations > 新查询

1. 先看 context.skills，description 匹配就填 entity_type="skill"
2. 再看 context.capabilities，匹配就填 entity_type="capability"
3. 再看 context.operations，匹配就 entity_id 留空，reason 说明操作名
4. 都不匹配 → entity_id 留空，并把合并后的完整分析目标写入 goal。

# SQL 生成边界
- 你绝不生成 SQL：sql 必须始终为 null。
- 只有后续拿到完整 schema 的查询生成器可以生成 SQL；这样确认卡和执行器只有一个 SQL 来源。
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
- 所有后续查询都走 A 路径：参考安全的历史 goal/参数化 SQL，重新生成完整 SQL，
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

    payload, _ = llm_provider.chat_json(llm_messages, temperature=0)
    plan = _parse_payload(payload, message)
    return _normalize(plan, message)


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

    # 无提案 → 直接回复（不走分析流程）
    if not proposal:
        # 检测 LLM 漏掉了数据分析请求
        if looks_like_safe_data_analysis_request(message):
            proposal = _repair_to_proposal(message)
            if proposal:
                return _validate_proposal(proposal, message, operation_registry, skill_registry, warnings=["模型未提出分析请求，系统已自动修复"])

        # 普通对话 → direct_response，不调用任何工具
        return ResponseValidationResult(
            allowed=True,
            route="direct_response",
            status="chat",
            user_goal=message.strip(),
        )

        return ResponseValidationResult(
            allowed=True,
            route="direct_response",
            status="chat",
            user_goal=message.strip(),
        )

    # 统一走 A 路径：即使旧客户端/模型带了 result_ref，也不能触发
    # “直接读取上一次结果”的 B 路径。历史查询会通过安全的 goal、参数化
    # SQL 和用户消息提供给后续规划器，后端随后重新生成并执行 SQL。
    legacy_refs = list(proposal.result_refs or [])
    proposal.result_refs = []
    if legacy_refs:
        proposal.reason = proposal.reason or "忽略旧结果引用，按当前数据重新生成并执行查询"

    validation = _validate_proposal(proposal, message, operation_registry, skill_registry)
    if legacy_refs:
        validation.warnings.append("当前统一按 A 路径处理：忽略旧结果引用，按最新数据重新查询")
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
        # A 路径不把内部结果句柄交给后续路由。
        result_refs=[],
        goal=user_goal,
        base_query_candidate=proposal.base_query_candidate,
        preferred_runtime=proposal.preferred_runtime,
        reason=proposal.reason,
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


def _repair_to_proposal(message: str) -> MethodProposal | None:
    """当 LLM 漏掉分析请求时，尝试修复。"""
    if looks_like_safe_data_analysis_request(message):
        return MethodProposal(
            goal=message.strip(),
            preferred_runtime="auto",
            reason="系统修复：模型未提出分析请求",
        )
    return None


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




# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def looks_like_safe_data_analysis_request(message: str) -> bool:
    text = message.strip().lower()
    if not text:
        return False
    analysis_terms = ["统计", "查询", "计算", "分析", "对比", "排名", "top", "最多", "最少", "方差", "标准差", "趋势", "分布", "多少笔", "count", "sum", "avg"]
    domain_terms = ["交易", "卡", "渠道", "消费", "金额", "客户", "状态", "transaction", "card", "amount", "status", "account"]
    return any(term in text for term in analysis_terms) and any(term in text for term in domain_terms)


def infer_skill_id_for_message(message: str) -> str | None:
    text = message.strip().lower()
    if any(term in message for term in ["交易质量", "失败交易", "异常状态", "成功率"]) or any(term in text for term in ["transaction quality", "failed transaction", "success rate"]):
        return "transaction_quality_review"
    if any(term in message for term in ["业务好不好", "业务健康", "分析业务", "业务表现"]):
        return "business_health_analysis"
    if any(term in message for term in ["卡渠道", "渠道表现", "渠道分析"]):
        return "channel_performance_analysis"
    return None
