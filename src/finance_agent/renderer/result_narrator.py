from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field

from finance_agent.config import Settings
from finance_agent.harness.analysis_schema import ExecutionResultCard, MethodDraft
from finance_agent.llm.provider import LlmProvider, build_llm_provider
from finance_agent.memory.safe_summary import infer_result_shape


class VariableDef(BaseModel):
    """变量定义：LLM 写的占位符及其值。"""
    value: str | int | float
    source: str = ""  # "data[0].count" 或 "computed: failed(5) + reversed(5)"


class SafeResultSummary(BaseModel):
    """给 LLM 的安全摘要，现在包含真实数据值。"""
    result_ref: str | None = None
    method_name: str
    method_type: str
    operation: str
    goal: str
    fields: list[str]
    row_count: int
    result_shape: dict[str, Any]
    execution_mode: str
    real_database_used: bool
    values_visible_to_llm: bool = True  # 现在 LLM 可以看到值
    result_data: list[dict[str, Any]] | dict[str, Any] | None = None  # 真实数据
    evidence_summary: dict[str, Any] = Field(default_factory=dict)


class ResultNarration(BaseModel):
    """LLM 输出的叙述，带变量模板。"""
    title: str
    summary: str
    variables: dict[str, VariableDef] = Field(default_factory=dict)
    key_findings: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    source: str = "lmstudio"


SYSTEM_PROMPT = """你是本地金融数据分析 Agent 的结果解读器。
你会收到沙箱执行的真实数据结果。你的任务是写出一段简洁的业务解读。

# 输出格式
{
  "title": "简短中文标题",
  "summary": "一段完整的中文解读，包含关键发现、注意事项和建议。用 {变量名} 引用数字。",
  "variables": {
    "变量名": {"value": 实际值, "source": "data[i].field 或 computed"}
  }
}

# 变量规则
- summary 中所有数字必须用 {变量名} 占位，不能直接写数字。
- variables 中定义每个变量的 value（必须与真实数据一致）和 source。
- 变量值必须与 result_data 严格一致，不能编造。

# summary 写法
- 用 2-4 句话写完，不要分点列举。
- 包含：主要发现、异常项（如有）、是否模拟数据、建议下一步。
- 用业务语言，不要说"数据已生成"或"结果如下"。
- 分布类：说明最大/最小项、占比、异常项。
- 趋势类：说明方向、幅度。
- 方差类：说明波动程度。
"""


def narrate_execution_result(
    card: ExecutionResultCard,
    method: MethodDraft,
    settings: Settings,
    llm_provider: LlmProvider | None = None,
    result_ref: str | None = None,
) -> ResultNarration:
    safe_summary = build_safe_result_summary(card, method, result_ref=result_ref)

    # 第一次尝试：完整 prompt
    narration = None
    try:
        narration = narrate_execution_result_with_lmstudio(safe_summary, settings, llm_provider)
    except Exception:
        pass

    # 第二次尝试：简化 prompt（去掉 variables 要求，只要 summary）
    if narration is None:
        try:
            narration = _narrate_simple(safe_summary, settings, llm_provider)
        except Exception:
            pass

    # 兜底
    if narration is None:
        narration = fallback_narration(safe_summary)

    # 验证并替换变量
    if safe_summary.result_data is not None and narration.variables:
        try:
            narration = validate_and_substitute_variables(narration, safe_summary.result_data)
        except Exception:
            pass

    return narration


def _narrate_simple(
    safe_summary: SafeResultSummary,
    settings: Settings,
    llm_provider: LlmProvider | None = None,
) -> ResultNarration:
    """简化版叙述：只要 title + summary，不要求 variables。"""
    simple_prompt = """你是结果解读器。根据下方数据写一段简洁的中文解读。
输出 JSON：
{"title": "标题", "summary": "2-4 句话解读，包含主要发现、异常项、是否模拟数据"}
不要编造数据中不存在的数字。"""
    messages = [
        {"role": "system", "content": simple_prompt},
        {"role": "user", "content": json.dumps(
            {"result_data": safe_summary.result_data, "goal": safe_summary.goal, "operation": safe_summary.operation},
            ensure_ascii=False,
        )},
    ]
    provider = llm_provider or build_llm_provider(settings)
    parsed, _ = provider.chat_json(messages, temperature=0.2, max_tokens=500, timeout_seconds=settings.result_narration_timeout_seconds)
    return ResultNarration(
        title=parsed.get("title", "分析结果"),
        summary=parsed.get("summary", ""),
        source="lmstudio_simple",
    )


def narrate_execution_result_with_lmstudio(
    safe_summary: SafeResultSummary,
    settings: Settings,
    llm_provider: LlmProvider | None = None,
) -> ResultNarration:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(
                {"safe_result_summary": safe_summary.model_dump(mode="json")},
                ensure_ascii=False,
            ),
        },
    ]
    provider = llm_provider or build_llm_provider(settings)
    parsed, response = provider.chat_json(
        messages,
        temperature=0.2,
        max_tokens=1200,
        timeout_seconds=settings.result_narration_timeout_seconds,
    )
    narration = ResultNarration.model_validate(parsed)
    narration.source = response.provider
    return narration


def build_safe_result_summary(
    card: ExecutionResultCard,
    method: MethodDraft,
    result_ref: str | None = None,
) -> SafeResultSummary:
    return SafeResultSummary(
        result_ref=result_ref,
        method_name=method.name,
        method_type=method.method_type,
        operation=method.operation,
        goal=method.goal,
        fields=card.data_authorization.fields,
        row_count=card.row_count,
        result_shape=infer_result_shape(card.result),
        execution_mode=card.execution_mode,
        real_database_used=card.real_database_used,
        values_visible_to_llm=True,
        result_data=card.result,  # 现在包含真实数据
        evidence_summary={
            "sandbox_runner": card.evidence.get("sandbox_runner"),
            "method_type": card.evidence.get("method_type"),
            "fixture": card.evidence.get("fixture"),
            "execution_error_count": len(card.evidence.get("execution_errors") or []),
        },
    )


def validate_and_substitute_variables(
    narration: ResultNarration,
    result_data: list[dict[str, Any]] | dict[str, Any],
) -> ResultNarration:
    """验证 LLM 定义的变量是否与真实数据一致，然后替换文本中的占位符。"""
    if not narration.variables:
        return narration

    data = result_data if isinstance(result_data, list) else [result_data]
    validated_vars: dict[str, str] = {}

    for var_name, var_def in narration.variables.items():
        value = var_def.value
        source = var_def.source

        # 验证 source 引用的值是否与 data 一致
        if source.startswith("data["):
            match = re.match(r"data\[(\d+)\]\.(\w+)", source)
            if match:
                idx, field = int(match.group(1)), match.group(2)
                if idx < len(data) and field in data[idx]:
                    actual = data[idx][field]
                    if _values_match(value, actual):
                        validated_vars[var_name] = str(value)
                    else:
                        # LLM 写的值与真实数据不一致，用真实值
                        validated_vars[var_name] = str(actual)
                else:
                    validated_vars[var_name] = str(value)
            else:
                validated_vars[var_name] = str(value)
        else:
            # computed 或其他来源，直接信任（LLM 在看数据后计算的）
            validated_vars[var_name] = str(value)

    # 替换文本中的 {变量名}
    result = narration.model_copy()
    result.title = _substitute_vars(result.title, validated_vars)
    result.summary = _substitute_vars(result.summary, validated_vars)
    result.key_findings = [_substitute_vars(f, validated_vars) for f in result.key_findings]
    result.caveats = [_substitute_vars(c, validated_vars) for c in result.caveats]
    result.next_steps = [_substitute_vars(s, validated_vars) for s in result.next_steps]
    return result


def _values_match(llm_value: Any, actual_value: Any) -> bool:
    """比较 LLM 写的值和真实值是否一致。"""
    if isinstance(llm_value, (int, float)) and isinstance(actual_value, (int, float)):
        return abs(float(llm_value) - float(actual_value)) < 0.01
    return str(llm_value) == str(actual_value)


def _substitute_vars(text: str, variables: dict[str, str]) -> str:
    """替换文本中的 {变量名} 为实际值。"""
    def replacer(match: re.Match) -> str:
        var_name = match.group(1)
        return variables.get(var_name, match.group(0))  # 未找到变量时保留原文

    return re.sub(r"\{(\w+)\}", replacer, text)


def fallback_narration(safe_summary: SafeResultSummary) -> ResultNarration:
    findings = _fallback_findings(safe_summary)
    caveats = [
        "本次没有连接真实数据库，结果来自 simulated 数据集，仅用于验证执行链路。"
        if not safe_summary.real_database_used
        else "本次结果来自已授权的数据范围。",
    ]
    return ResultNarration(
        title="执行结果解读",
        summary=f"沙箱已完成 {safe_summary.goal}。",
        key_findings=findings,
        caveats=caveats,
        next_steps=[],
        source="fallback",
    )


def _fallback_findings(safe_summary: SafeResultSummary) -> list[str]:
    shape = safe_summary.result_shape
    if shape.get("kind") == "rows":
        columns = ", ".join(shape.get("columns") or [])
        return [f"结果已生成，列为：{columns}。"]
    keys = ", ".join(shape.get("keys") or [])
    return [f"结果已生成，字段为：{keys}。"]
