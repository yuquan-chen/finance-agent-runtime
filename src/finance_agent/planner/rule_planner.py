from __future__ import annotations

from finance_agent.harness.plan_schema import Filter, Intent, Metric, OrderBy, QueryPlan
from finance_agent.metadata.catalog import Catalog


def _choose_table(catalog: Catalog, preferred: str = "card_transaction") -> str:
    if catalog.table(preferred):
        return preferred
    if not catalog.tables:
        raise ValueError("visible catalog has no tables")
    return catalog.tables[0].name


def plan_with_rules(query: str, visible_catalog: Catalog) -> QueryPlan:
    lowered = query.lower()
    table = _choose_table(visible_catalog)
    if ("渠道" in query or "channel" in lowered) and ("最后" in query or "最近" in query or "last" in lowered):
        return QueryPlan(
            intent=Intent.latest_by_group,
            table=table,
            group_by="card_channel",
            order_by=[
                OrderBy(field="transaction_at", direction="desc"),
                OrderBy(field="complete_at", direction="desc"),
                OrderBy(field="channel_complete_at", direction="desc"),
                OrderBy(field="created_at", direction="desc"),
                OrderBy(field="id_no", direction="desc"),
                OrderBy(field="id", direction="desc"),
            ],
            limit=50,
            rationale="Rule planner matched card channel latest transaction query.",
        )
    if ("渠道" in query or "channel" in lowered) and ("几个" in query or "多少" in query or "count" in lowered):
        return QueryPlan(
            intent=Intent.count_distinct,
            table=table,
            group_by="card_channel",
            limit=50,
            rationale="Rule planner matched card channel count query.",
        )
    if "消费最多" in query or "top consumption" in lowered or "largest consumption" in lowered:
        return QueryPlan(
            intent=Intent.top_n,
            table=table,
            group_by="account_id",
            metrics=[Metric(field="total_amount", op="sum", alias="total_consumption")],
            filters=[
                Filter(field="type", op="in", value=["consumption", "consume", "purchase"]),
                Filter(field="status", op="in", value=["completed", "success", "succeeded", "settled"]),
            ],
            order_by=[OrderBy(field="total_consumption", direction="desc")],
            limit=1,
            rationale="Rule planner matched top consumption customer query.",
        )
    raise ValueError("No rule planner match. The runtime should ask for clarification or refuse safely.")
