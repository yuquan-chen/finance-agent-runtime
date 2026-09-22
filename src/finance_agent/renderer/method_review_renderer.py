"""方法审查与结果渲染（声明型）。

findings 解读使用通用逻辑，不再依赖 handler 函数。
所有渲染函数返回结构化数据，由 reply_generator 调用 LLM 生成最终回复。
"""
from __future__ import annotations

from typing import Any

from finance_agent.audit.audit_logger import stable_hash
from finance_agent.harness.analysis_schema import (
    AnalysisPlan,
    DataAuthorizationCard,
    ExecutionResultCard,
    MethodDraft,
    MethodReviewCard,
    MethodSetReviewCard,
    MockDryRunResult,
    PriorResultAuthorizationCard,
)
from finance_agent.operations.handler_registry import (
    OperationHandlerRegistry,
    get_default_registry,
)
from finance_agent.renderer.result_narrator import ResultNarration


def build_method_review_card(method: MethodDraft, mock_result) -> MethodReviewCard:
    return MethodReviewCard(
        method_name=method.name,
        method_type=method.method_type,
        goal=method.goal,
        required_fields=method.required_fields,
        logic_summary=method.logic_summary,
        mock_result=mock_result,
        risk_level=method.risk_level,
        approval_required=True,
    )


def build_method_set_review_card(
    plan: AnalysisPlan,
    cards: list[MethodReviewCard],
) -> MethodSetReviewCard:
    """构造一个覆盖全部步骤的确认卡，而不是为每个步骤创建确认按钮。"""
    fields: list[str] = []
    seen: set[str] = set()
    for card in cards:
        for field in card.required_fields:
            if field not in seen:
                seen.add(field)
                fields.append(field)
    risks = {card.risk_level for card in cards}
    risk_level = "high" if "high" in risks else ("medium" if "medium" in risks else "low")
    return MethodSetReviewCard(
        goal=plan.goal,
        steps=cards,
        required_fields=fields,
        logic_summary=[f"共 {len(cards)} 个独立分析步骤，确认后按顺序执行。"],
        risk_level=risk_level,
        approval_required=True,
    )


def render_method_review_data(
    plan: AnalysisPlan,
    method: MethodDraft,
    card: MethodReviewCard,
    prior_queries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """渲染单步骤方法审查数据"""
    return {
        "type": "method_review",
        "method_name": card.method_name,
        "method_type": card.method_type,
        "goal": card.goal,
        "field_count": len(card.required_fields),
        "fields": card.required_fields,
        "logic_summary": card.logic_summary,
        "sql_template": method.sql_template,
        "code": method.code,
        "requires_authorization": card.approval_required,
        "prior_queries": prior_queries or [],
    }


def render_method_set_review_data(
    plan: AnalysisPlan,
    methods: list[MethodDraft],
    cards: list[MethodReviewCard],
    registry: OperationHandlerRegistry | None = None,
) -> dict[str, Any]:
    """渲染多步骤方法审查数据"""
    registry = registry or get_default_registry()
    steps_data = []
    all_fields: list[str] = []
    seen: set[str] = set()

    for method, card in zip(methods, cards, strict=False):
        handler = registry.get(method.operation)
        title = handler.title if handler else method.name
        steps_data.append({
            "method_name": card.method_name,
            "title": title,
            "goal": card.goal,
            "logic_summary": card.logic_summary,
            "sql_template": method.sql_template,
            "code": method.code,
        })
        for field in card.required_fields:
            if field not in seen:
                seen.add(field)
                all_fields.append(field)

    return {
        "type": "method_set_review",
        "step_count": len(steps_data),
        "steps": steps_data,
        "field_count": len(all_fields),
        "fields": all_fields,
        "requires_authorization": True,
    }


def build_data_authorization_card(method: MethodDraft, row_limit: int = 1000) -> DataAuthorizationCard:
    tables = sorted({field.split(".", 1)[0] for field in method.required_fields if "." in field})
    return DataAuthorizationCard(
        status="pending",
        purpose=method.goal,
        method_name=method.name,
        method_hash=stable_hash(method.model_dump(mode="json")),
        tables=tables or [method.table],
        fields=method.required_fields,
        row_limit=row_limit,
        readonly=True,
        real_data_read=False,
        safety_notes=[],
    )


def build_data_authorization_card_for_methods(methods: list[MethodDraft], row_limit: int = 1000) -> DataAuthorizationCard:
    fields = sorted({field for method in methods for field in method.required_fields})
    tables = sorted({field.split(".", 1)[0] for field in fields if "." in field})
    method_hash = stable_hash([method.model_dump(mode="json") for method in methods])
    purpose = methods[0].goal if methods else ""
    method_name = "method_set" if len(methods) != 1 else methods[0].name
    return DataAuthorizationCard(
        status="pending",
        purpose=purpose,
        method_name=method_name,
        method_hash=method_hash,
        tables=tables or sorted({method.table for method in methods}) or ["card_transaction"],
        fields=fields,
        row_limit=row_limit,
        readonly=True,
        real_data_read=False,
        safety_notes=[],
    )


def render_prior_result_authorization_data(card: PriorResultAuthorizationCard) -> dict[str, Any]:
    """渲染基于 prior result 的授权数据"""
    return {
        "type": "prior_result_authorization",
        "purpose": card.purpose,
        "method_name": card.method_name,
        "referenced_result_ref": card.referenced_result_ref,
        "prior_result_fields": card.prior_result_fields,
        "prior_result_row_count": card.prior_result_row_count,
        "operation": card.operation,
        "new_database_access": card.new_database_access,
        "requires_authorization": True,
    }


def render_data_authorization_data(card: DataAuthorizationCard, sql_template: str | None = None) -> dict[str, Any]:
    """渲染数据授权数据"""
    return {
        "type": "data_authorization",
        "tables": card.tables,
        "field_count": len(card.fields),
        "fields": card.fields,
        "row_limit": card.row_limit,
        "readonly": card.readonly,
        "requires_authorization": True,
        "sql_template": sql_template,
    }


def build_execution_result_card(
    method: MethodDraft,
    authorization: DataAuthorizationCard,
    execution_result: MockDryRunResult,
) -> ExecutionResultCard:
    output = execution_result.output if execution_result.output is not None else {}
    # The result card describes returned rows, not fixture rows loaded into the
    # sandbox. Aggregate queries can read 100 rows and return one row.
    row_count = len(output) if isinstance(output, list) else (1 if isinstance(output, dict) else 0)
    execution_mode = str(execution_result.input_summary.get("execution_mode") or "simulated_real")
    if execution_mode not in {"simulated_real", "direct_db", "safe_db"}:
        execution_mode = "simulated_real"
    return ExecutionResultCard(
        status="executed",
        execution_mode=execution_mode,
        method_name=method.name,
        method_hash=stable_hash(method.model_dump(mode="json")),
        data_authorization=authorization,
        result=output,
        row_count=row_count,
        evidence={
            "sql_template": method.sql_template,
            "method_type": method.method_type,
            "sandbox_runner": execution_result.input_summary.get("runner"),
            "fixture": execution_result.input_summary.get("fixture"),
            "execution_errors": execution_result.errors,
        },
        real_database_used=bool(execution_result.input_summary.get("real_database_used", False)),
    )


def render_execution_result_data(
    card: ExecutionResultCard,
    narration: ResultNarration | None = None,
    registry: OperationHandlerRegistry | None = None,
) -> dict[str, Any]:
    """渲染执行结果数据"""
    findings = build_deterministic_result_findings(card)
    return {
        "type": "execution_result",
        "method_name": card.method_name,
        "method_type": card.evidence.get("method_type"),
        "sql_template": card.evidence.get("sql_template"),  # 添加真正执行的 SQL
        "result_count": len(card.result) if isinstance(card.result, list) else 1,
        "result": card.result,
        "findings": findings,
        "execution_mode": card.execution_mode,
        "narration_summary": narration.summary if narration else None,
        "narration_title": narration.title if narration else None,
    }


def render_execution_result_set_data(
    cards: list[ExecutionResultCard],
    narrations: list[ResultNarration | None] | None = None,
    registry: OperationHandlerRegistry | None = None,
) -> dict[str, Any]:
    """渲染多步骤执行结果数据"""
    narrations = narrations or [None] * len(cards)
    steps_data = []

    for index, (card, narration) in enumerate(zip(cards, narrations, strict=False), start=1):
        findings = build_deterministic_result_findings(card)
        steps_data.append({
            "step_index": index,
            "method_name": card.method_name,
            "method_type": card.evidence.get("method_type"),
            "sql_template": card.evidence.get("sql_template"),  # 添加真正执行的 SQL
            "result_count": len(card.result) if isinstance(card.result, list) else 1,
            "result": card.result,
            "findings": findings,
            "execution_mode": card.execution_mode,
            "narration_summary": narration.summary if narration else None,
        })

    return {
        "type": "execution_result_set",
        "step_count": len(steps_data),
        "steps": steps_data,
    }


def refuse_method_data(error: str) -> dict[str, Any]:
    """渲染拒绝方法数据"""
    return {
        "type": "refuse",
        "error": error,
        "requires_authorization": False,
    }


# ---------------------------------------------------------------------------
# 通用 findings（不依赖 handler）
# ---------------------------------------------------------------------------

def _num(value: float) -> str:
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def _pct(value: float, total: float) -> str:
    if total == 0:
        return "无法计算"
    return f"{value / total * 100:.2f}%"


def build_deterministic_result_findings(card: ExecutionResultCard) -> list[str]:
    """通用 findings 解读（基于结果结构推断）。"""
    result = card.result
    if not isinstance(result, list) or not result:
        return []

    columns = set(result[0].keys())

    # 分布型：有 count 或 record_count 列
    count_cols = {"count", "record_count"}
    if any(c in count_cols for c in columns) and len(columns) >= 2:
        return _distribution_findings(result)

    # 趋势型：有 bucket 列
    if "bucket" in columns:
        return _trend_findings(result)

    # 排名型：有数值列
    numeric_cols = {"total_amount", "total_value", "settle_amount", "origin_amount", "amount"}
    if any(c in numeric_cols for c in columns):
        return _top_n_findings(result)

    # 方差型：有 mean 和 variance
    if {"mean", "variance"}.issubset(columns):
        return _variance_findings(result)

    return []


def _distribution_findings(rows: list[dict]) -> list[str]:
    """分布型 findings。"""
    # 支持 count 和 record_count 两种列名
    count_key = "count" if "count" in rows[0] else "record_count"
    total = sum(int(r.get(count_key, 0)) for r in rows)
    if total == 0:
        return []
    top = rows[0]
    top_key = next((v for k, v in top.items() if k != count_key and isinstance(v, str)), "-")
    top_count = int(top.get(count_key, 0))
    return [
        f"当前结果中 {top_key} 最多，共 {_num(top_count)} 条，占 {_pct(top_count, total)}。",
        f"共 {len(rows)} 个分组，总计 {_num(total)} 条。",
    ]


def _trend_findings(rows: list[dict]) -> list[str]:
    """趋势型 findings。"""
    values = []
    for row in rows:
        bucket = str(row.get("bucket", "-"))
        metric_val = None
        for k, v in row.items():
            if k != "bucket" and isinstance(v, (int, float)):
                metric_val = float(v)
                break
        if metric_val is not None:
            values.append((bucket, metric_val))
    if len(values) < 2:
        return []
    first_bucket, first_value = values[0]
    last_bucket, last_value = values[-1]
    delta = last_value - first_value
    direction = "上升" if delta > 0 else ("下降" if delta < 0 else "持平")
    return [
        f"从 {first_bucket} 到 {last_bucket}，指标由 {_num(first_value)} 变为 {_num(last_value)}，整体{direction}。",
        f"变化量为 {_num(delta)}，变化幅度 {_pct(delta, first_value) if first_value else '无法计算'}。",
    ]


def _top_n_findings(rows: list[dict]) -> list[str]:
    """排名型 findings。"""
    normalized: list[tuple[str, float]] = []
    for row in rows:
        key = "-"
        value = None
        for item in row.values():
            if isinstance(item, str) and key == "-":
                key = item
            elif isinstance(item, (int, float)) and value is None:
                value = item
        if value is not None:
            normalized.append((str(key), float(value)))
    if not normalized:
        return []
    total = sum(value for _, value in normalized)
    top_key, top_value = normalized[0]
    findings = [f"当前结果中排名第一的是 {top_key}，指标值为 {_num(top_value)}。"]
    if total > 0:
        top3 = sum(value for _, value in normalized[:3])
        findings.append(f"Top 3 合计占当前返回结果的 {_pct(top3, total)}，可用于观察集中度。")
    return findings


def _variance_findings(rows: list[dict]) -> list[str]:
    """方差型 findings。"""
    row = rows[0] if rows else {}
    findings = []
    if "mean" in row:
        findings.append(f"均值为 {_num(float(row['mean']))}。")
    if "variance" in row:
        findings.append(f"总体方差为 {_num(float(row['variance']))}，数值越大表示波动越明显。")
    return findings
