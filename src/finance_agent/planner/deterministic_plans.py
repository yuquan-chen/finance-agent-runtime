"""Deterministic query plans for high-value, repeatable business questions."""
from __future__ import annotations

from finance_agent.harness.analysis_schema import AnalysisPlan, AnalysisStep
from finance_agent.metadata.catalog import Catalog


def build_deterministic_plan(
    goal: str,
    visible: Catalog,
    input_slots: list[dict[str, str]] | None = None,
    query_context: str = "",
) -> AnalysisPlan | None:
    """Build a plan when the business shape is unambiguous.

    The LLM may still normalize the user's wording, but it must not choose the
    join, aggregation, or ordering for this common ranking query.
    """
    # The routing stage may normalize away product/source qualifiers such as
    # "VA". Keep the original question as a local intent hint so the planner
    # cannot silently switch to another transaction type.
    text = " ".join(f"{goal or ''} {query_context or ''}".casefold().split())
    customer_slot = _customer_name_slot(input_slots)
    if not _is_customer_transaction_ranking(text) and not (
        customer_slot and _is_customer_transaction_query(text)
    ):
        return None

    source_table = _choose_transaction_table(text, visible)
    if source_table is None or visible.table("account") is None:
        return None
    source = visible.table(source_table)
    account = visible.table("account")
    if source is None or account is None:
        return None
    # The template uses these fields with fixed business meaning. Do not emit
    # a plausible-looking query when the selected table has not been mapped.
    if "account_id" not in source.column_names or "transaction_at" not in source.column_names:
        return None
    if not {"id", "legal_name", "legal_name_en"}.issubset(account.column_names):
        return None

    time_slots = [
        slot for slot in (input_slots or [])
        if slot.get("bound_part") in {"start", "end"}
        and slot.get("type") in {"date", "datetime"}
    ]
    if len(time_slots) >= 2:
        start_slot = next(slot["id"] for slot in time_slots if slot["bound_part"] == "start")
        end_slot = next(slot["id"] for slot in time_slots if slot["bound_part"] == "end")
        time_filter = (
            f"WHERE tx.transaction_at >= :{start_slot} "
            f"AND tx.transaction_at < :{end_slot}"
        )
    else:
        time_filter = ""

    if _is_amount_ranking(text):
        if "total_amount" not in source.column_names:
            return None
        metric_sql = "SUM(COALESCE(tx.total_amount, 0)) AS transaction_amount"
        order_alias = "transaction_amount"
        metric_name = "交易金额"
    else:
        metric_sql = "COUNT(*) AS transaction_count"
        order_alias = "transaction_count"
        metric_name = "交易笔数"

    customer_filter = ""
    if customer_slot:
        customer_field = customer_slot["id"]
        customer_filter = (
            f"a.legal_name = :{customer_field} "
            f"OR a.legal_name_en = :{customer_field}"
        )

    # Customer-scoped queries must resolve the name on account first. The
    # transaction table's account_id is only the join key, never the customer
    # name filter itself.
    where_parts = [part for part in (time_filter.removeprefix("WHERE "), customer_filter) if part]
    where_sql = f"WHERE {' AND '.join(f'({part})' for part in where_parts)}" if where_parts else ""

    is_scoped_customer_query = bool(customer_slot and _is_customer_transaction_query(text))
    if is_scoped_customer_query and not _is_customer_transaction_ranking(text):
        sql = (
            "SELECT COALESCE(NULLIF(a.legal_name, ''), a.legal_name_en) AS customer_name, "
            "COUNT(*) AS transaction_count "
            f"FROM {source_table} tx "
            "JOIN account a ON a.id = tx.account_id "
            f"{where_sql} "
            "GROUP BY a.id, a.legal_name, a.legal_name_en"
        ).strip()
        return AnalysisPlan(
            goal=goal,
            assumptions=[
                f"{source_table} 通过 account_id 关联 account.id",
                "客户名称在 account.legal_name / account.legal_name_en 上匹配",
                "交易量按交易笔数计算",
            ],
            steps=[
                AnalysisStep(
                    operation="group_by",
                    table=source_table,
                    dimension="customer_name",
                    group_by="account_id",
                    time_field="transaction_at" if time_filter else None,
                    sql=sql,
                    rationale="先按客户名称定位 account，再统计该客户的 VA 交易笔数。",
                )
            ],
            required_metadata=[
                f"{source_table}.account_id",
                "account.id",
                "account.legal_name",
                "account.legal_name_en",
            ],
            requires_method_generation=True,
            rationale="命中客户名称过滤的确定性交易查询模板。",
        )

    sql = (
        "SELECT COALESCE(NULLIF(a.legal_name, ''), a.legal_name_en) AS customer_name, "
        f"{metric_sql} "
        f"FROM {source_table} tx "
        "JOIN account a ON a.id = tx.account_id "
        f"{where_sql} "
        "GROUP BY a.id, a.legal_name, a.legal_name_en "
        f"ORDER BY {order_alias} DESC, a.id ASC "
        "LIMIT 1"
    )
    required_metadata = [
        f"{source_table}.account_id",
        f"{source_table}.transaction_at",
        "account.id",
        "account.legal_name",
        "account.legal_name_en",
    ]
    if _is_amount_ranking(text):
        required_metadata.append(f"{source_table}.total_amount")

    return AnalysisPlan(
        goal=goal,
        assumptions=[
            f"{source_table} 通过 account_id 关联 account.id",
            f"交易量按{metric_name}计算",
            "按指标倒序取第一名；同值时按 account.id 稳定排序",
        ],
        steps=[
            AnalysisStep(
                operation="customer_transaction_top_n",
                table=source_table,
                metric="total_amount" if _is_amount_ranking(text) else None,
                dimension="customer_name",
                group_by="account_id",
                time_field="transaction_at",
                limit=1,
                sql=sql,
                rationale="后端固定客户维度、交易表到账户表的关联、时间范围、聚合和排序。",
            )
        ],
        required_metadata=required_metadata,
        requires_method_generation=True,
        rationale="命中确定性客户交易排名模板。",
    )


def _is_customer_transaction_ranking(text: str) -> bool:
    return (
        _contains_any(text, ("客户", "客户名", "客户名称", "公司", "企业"))
        and _contains_any(text, ("交易", "支付", "付款", "转账"))
        and _contains_any(text, ("最多", "最高", "最大", "排名", "top"))
    )


def _is_customer_transaction_query(text: str) -> bool:
    """Whether the request scopes a transaction query to one customer."""
    return (
        _contains_any(text, ("客户", "客户名", "客户名称", "公司", "企业"))
        and _contains_any(text, ("交易", "支付", "付款", "转账"))
    )


def _customer_name_slot(input_slots: list[dict[str, str]] | None) -> dict[str, str] | None:
    """Find the opaque text slot representing a customer/company name."""
    for slot in input_slots or []:
        semantic = " ".join(
            str(slot.get(key) or "").casefold()
            for key in ("source_param", "semantic")
        )
        if slot.get("type") == "text" and _contains_any(
            semantic, ("客户", "公司", "企业", "名称", "customer", "company", "name")
        ):
            return slot
    return None


def _is_amount_ranking(text: str) -> bool:
    return _contains_any(text, ("金额", "交易额", "总额", "gmv", "amount"))


def _contains_any(text: str, values: tuple[str, ...]) -> bool:
    return any(value.casefold() in text for value in values)


def _choose_transaction_table(text: str, catalog: Catalog) -> str | None:
    """Choose a source only when the business object is explicit or unique."""
    explicit_sources = (
        (("va", "虚拟账户"), "va_transaction"),
        (("卡", "card"), "card_transaction"),
        (("付款", "打款", "汇款", "payout"), "payout_transaction"),
        (("支付", "收款", "payment"), "pay_transaction"),
    )
    for hints, table_name in explicit_sources:
        if _contains_any(text, hints) and catalog.table(table_name) is not None:
            return table_name

    candidates = [
        name
        for name in ("card_transaction", "va_transaction", "pay_transaction", "payout_transaction", "transaction")
        if catalog.table(name) is not None
    ]
    return candidates[0] if len(candidates) == 1 else None
