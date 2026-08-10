from __future__ import annotations

import json
from typing import Any

from finance_agent.config import Settings
from finance_agent.harness.plan_schema import QueryPlan
from finance_agent.llm.provider import LlmProvider, build_llm_provider
from finance_agent.metadata.catalog import Catalog


SYSTEM_PROMPT = """You are the Architect in a finance data agent runtime.
You must output only a JSON object that matches the QueryPlan schema.
You never output SQL. You never output final numbers. You never assume data values.
You can only use tables and columns visible in the provided metadata.
Supported intents: latest_by_group, top_n, count_distinct, aggregate_by_group.
"""


def catalog_for_prompt(catalog: Catalog) -> dict[str, Any]:
    return {
        "version": catalog.version,
        "tables": [
            {
                "name": table.name,
                "description": table.description,
                "allowed_intents": table.allowed_intents,
                "columns": [
                    {
                        "name": column.name,
                        "type": column.type,
                        "semantic": column.semantic,
                    }
                    for column in table.columns
                ],
                "relationships": [relationship.model_dump(by_alias=True) for relationship in table.relationships],
            }
            for table in catalog.tables
        ],
        "business_terms": catalog.business_terms,
    }


def plan_with_lmstudio(
    query: str,
    visible_catalog: Catalog,
    settings: Settings,
    llm_provider: LlmProvider | None = None,
) -> QueryPlan:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "user_query": query,
                    "visible_metadata": catalog_for_prompt(visible_catalog),
                    "query_plan_schema": {
                        "intent": "latest_by_group | top_n | count_distinct | aggregate_by_group",
                        "table": "visible table name",
                        "group_by": "visible column or null",
                        "metrics": [{"field": "visible column", "op": "sum|count|avg|min|max", "alias": "optional"}],
                        "filters": [{"field": "visible column", "op": "=|!=|in|>=|<=|>|<|between", "value": "literal"}],
                        "order_by": [{"field": "visible column or metric alias", "direction": "asc|desc"}],
                        "limit": 50,
                        "rationale": "brief reason",
                    },
                },
                ensure_ascii=False,
            ),
        },
    ]
    provider = llm_provider or build_llm_provider(settings)
    parsed, _ = provider.chat_json(messages, temperature=0, max_tokens=800)
    return QueryPlan.model_validate(parsed)
