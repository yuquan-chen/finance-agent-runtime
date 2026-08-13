from __future__ import annotations

from finance_agent.metadata.catalog import Catalog, TableMeta
from finance_agent.metadata.policy import Policy


CARD_TRANSACTION_HINTS = ["卡", "card", "交易", "transaction", "trx", "消费", "consumption", "渠道", "channel"]
PAYOUT_TRANSACTION_HINTS = ["付款", "打款", "汇款", "payout"]
PAY_TRANSACTION_HINTS = ["支付", "收款", "payment"]


def table_score(query: str, table: TableMeta, catalog: Catalog) -> int:
    lowered = query.lower()
    score = 0

    # 表名匹配
    if table.name.lower() in lowered:
        score += 10
    for token in table.name.lower().replace("_", " ").split():
        if token and token in lowered:
            score += 2

    # 特殊表加分
    if table.name == "card_transaction" and any(hint in query or hint in lowered for hint in CARD_TRANSACTION_HINTS):
        score += 8
    # “付款 / payout” 与 “支付 / payment” 是两类不同业务表，不能只靠英文表名模糊匹配。
    if table.name == "payout_transaction" and any(hint in query or hint in lowered for hint in PAYOUT_TRANSACTION_HINTS):
        score += 40
    if table.name == "pay_transaction" and any(hint in query or hint in lowered for hint in PAY_TRANSACTION_HINTS):
        score += 40

    # 列名匹配（支持部分匹配）
    for column in table.columns:
        col_lower = column.name.lower()

        # 精确匹配
        if col_lower in lowered:
            score += 4

        # 部分匹配：检查列名的每个部分是否在查询中
        for part in col_lower.split("_"):
            if len(part) >= 3 and part in lowered:
                score += 2

        # 检查列语义是否匹配
        if column.semantic:
            sem_lower = column.semantic.lower()
            for word in lowered.split():
                if len(word) >= 2 and word in sem_lower:
                    score += 1

        # 业务术语匹配
        for term, term_meta in catalog.business_terms.items():
            candidates = term_meta.get("candidate_fields", []) if isinstance(term_meta, dict) else []
            if column.name in candidates and (term in lowered or term in query):
                score += 3

    return score


def prune_catalog(query: str, catalog: Catalog, policy: Policy, max_tables: int = 10) -> Catalog:
    lowered = query.lower()
    scored = sorted(
        ((table_score(query, table, catalog), table) for table in catalog.tables),
        key=lambda item: item[0],
        reverse=True,
    )
    selected_tables = [table for score, table in scored if score > 0][:max_tables] or catalog.tables[:max_tables]
    # 客户名称过滤需要 account.legal_name；为交易类查询补上账户表，让规划器能生成合法 JOIN。
    needs_account = any(token in lowered for token in ("company", "person", "客户", "公司", "企业"))
    has_transaction = any(table.name in {"payout_transaction", "pay_transaction", "card_transaction"} for table in selected_tables)
    account = catalog.table("account")
    if needs_account and has_transaction and account and account not in selected_tables:
        selected_tables.append(account)
    sanitized_tables: list[TableMeta] = []
    for table in selected_tables:
        visible_columns = [
            column
            for column in table.columns
            if not column.sensitive and not policy.is_sensitive_column_name(column.name)
        ]
        sanitized_tables.append(table.model_copy(update={"columns": visible_columns}))
    return Catalog(
        version=catalog.version,
        description=catalog.description,
        tables=sanitized_tables,
        business_terms=catalog.business_terms,
    )
