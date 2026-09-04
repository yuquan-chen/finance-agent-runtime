from __future__ import annotations

from finance_agent.metadata.catalog import Catalog, TableMeta
from finance_agent.metadata.policy import Policy


def _text_units(value: str) -> set[str]:
    """Build generic searchable units from table-level text only."""
    normalized = value.casefold()
    units = {part for part in normalized.replace("_", " ").split() if part}
    for index in range(len(normalized) - 1):
        pair = normalized[index:index + 2]
        if all(
            ("\u4e00" <= char <= "\u9fff") or ("\u3400" <= char <= "\u4dbf")
            for char in pair
        ):
            units.add(pair)
    return units


def table_score(query: str, table: TableMeta, catalog: Catalog) -> int:
    lowered = query.lower()
    score = 0

    # 只使用表级元数据。字段会在选表后再展开，避免业务语言直接命中字段。
    if table.name.lower() in lowered:
        score += 10
    for token in table.name.lower().replace("_", " ").split():
        if token and token in lowered:
            score += 2

    # 中文描述没有天然空格，使用通用二字符片段参与表级匹配。
    score += 2 * len(_text_units(query) & _text_units(table.description))

    # 业务词典是可配置的表级映射，不在代码中维护业务分支。
    for term, term_meta in catalog.business_terms.items():
        if not isinstance(term_meta, dict):
            continue
        candidate_tables = term_meta.get("candidate_tables", [])
        if table.name not in candidate_tables:
            continue
        labels = [term, *(term_meta.get("aliases", []) or [])]
        if any(str(label).casefold() in lowered for label in labels if label):
            score += 20

    return score


def prune_catalog(query: str, catalog: Catalog, policy: Policy, max_tables: int = 10) -> Catalog:
    scored = sorted(
        ((table_score(query, table, catalog), table) for table in catalog.tables),
        key=lambda item: item[0],
        reverse=True,
    )
    selected_tables = [table for score, table in scored if score > 0][:max_tables] or catalog.tables[:max_tables]
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
