from __future__ import annotations

import json
from typing import Any

from finance_agent.config import Settings
from finance_agent.harness.analysis_schema import AnalysisPlan, AnalysisStep
from finance_agent.llm.provider import LlmProvider, build_llm_provider
from finance_agent.metadata.catalog import Catalog
from finance_agent.operations.registry import OperationRegistry


SYSTEM_PROMPT = """# 角色
你是金融数据分析 Agent 的分析计划器。
你的职责：根据用户目标，输出一组分析步骤（AnalysisPlan JSON）。
你不执行任何工具，不读取真实数据，不输出最终数字。

# 输出格式
{
  "mode": "analysis_plan",
  "goal": "分析目标",
  "assumptions": ["假设条件"],
  "steps": [
    {
      "operation": "操作名",
      "table": "表名",
      "metric": "指标字段或null",
      "dimension": "维度字段或null",
      "group_by": "分组字段或null",
      "time_field": "时间字段或null",
      "grain": "day|week|month|quarter|null",
      "limit": 10,
      "filters": [],
      "rationale": "为什么选这个步骤",
      "sql": "SELECT ... FROM ... GROUP BY ..."
    }
  ],
  "required_metadata": ["table.field"],
  "requires_method_generation": true,
  "rationale": "整体分析思路"
}

# 关键规则
1. 每个步骤必须有 sql 字段，写完整的 SELECT 语句
2. 表名和字段名来自 context.table_manifest（列名、类型都在里面）
3. 只写 SELECT，绝不写 INSERT/UPDATE/DELETE
4. 多表用 JOIN，关系参考 table_manifest 中的 relationships
5. 业务术语参考 context.business_terms（如"消费"= type='consumption'）
6. 参数用 :param_name 格式

# 步骤设计原则
- 从宏观到微观：先看整体趋势，再拆维度
- 每个步骤解决一个问题，不要把多个分析塞进步骤
- 常见组合：状态分布 + 时间趋势 + 维度拆分
- 如果用户指定了 skill，按 skill 的 suggested_capabilities 组织步骤

# 示例

用户目标："统计每个交易状态有多少笔"
→ {
  "mode": "analysis_plan",
  "goal": "统计交易状态分布",
  "steps": [{
    "operation": "status_distribution",
    "table": "card_transaction",
    "dimension": "status",
    "sql": "SELECT status, COUNT(*) AS count FROM card_transaction GROUP BY status ORDER BY count DESC",
    "rationale": "按状态分组统计笔数"
  }],
  "required_metadata": ["card_transaction.status"]
}

用户目标："业务健康度分析"
→ {
  "mode": "analysis_plan",
  "goal": "业务健康度分析",
  "steps": [
    {"operation": "trend", "table": "card_transaction", "metric": "total_amount", "time_field": "transaction_at", "grain": "month", "sql": "SELECT DATE_TRUNC('month', transaction_at) AS month, SUM(total_amount) FROM card_transaction GROUP BY month ORDER BY month", "rationale": "观察金额月度趋势"},
    {"operation": "status_distribution", "table": "card_transaction", "dimension": "status", "sql": "SELECT status, COUNT(*) FROM card_transaction GROUP BY status", "rationale": "观察状态分布"}
  ],
  "required_metadata": ["card_transaction.total_amount", "card_transaction.transaction_at", "card_transaction.status"]
}
"""


def _catalog_payload(catalog: Catalog) -> dict[str, Any]:
    return {
        "version": catalog.version,
        "tables": [
            {
                "name": table.name,
                "description": table.description,
                "columns": [
                    {
                        "name": column.name,
                        "type": column.type,
                        "semantic": column.semantic,
                        "sensitive": column.sensitive,
                    }
                    for column in table.columns
                ],
                "relationships": [
                    {
                        "from_field": rel.from_field,
                        "to": rel.to,
                        "type": rel.type,
                    }
                    for rel in table.relationships
                ],
            }
            for table in catalog.tables
        ],
        "business_terms": catalog.business_terms,
    }


def _operation_payload(registry: OperationRegistry) -> list[dict[str, Any]]:
    return [operation.model_dump() for operation in registry.operations]


def plan_analysis_with_lmstudio(
    query: str,
    visible_catalog: Catalog,
    operation_registry: OperationRegistry,
    settings: Settings,
    llm_provider: LlmProvider | None = None,
    action_context: dict[str, Any] | None = None,
    handler_manifest: list[dict[str, str]] | None = None,
    business_term_manifest: list[dict[str, Any]] | None = None,
    table_manifest: list[dict[str, Any]] | None = None,
) -> AnalysisPlan:
    payload: dict[str, Any] = {
        "user_query": query,
        "action_context": action_context or {},
        "visible_metadata": _catalog_payload(visible_catalog),
        "operation_registry": _operation_payload(operation_registry),
        "analysis_plan_schema": {
            "mode": "analysis_plan | single_operation | method_creation | clarification | refusal | help_response",
            "goal": "business goal",
            "assumptions": ["safe assumptions, no data values"],
            "steps": [
                {
                    "operation": "operation registry name",
                    "table": "visible table",
                    "metric": "visible metric column or null",
                    "dimension": "visible metric column or null",
                    "group_by": "visible grouping column or null",
                    "time_field": "visible timestamp column or null",
                    "grain": "day|week|month|quarter|null",
                    "limit": 10,
                    "filters": [],
                    "rationale": "why this step helps",
                    "sql": "REQUIRED: valid SELECT SQL statement using visible table/column names"
                }
            ],
            "required_metadata": ["table.field"],
            "requires_method_generation": True,
            "rationale": "brief reason",
        },
    }
    if handler_manifest:
        payload["handler_manifest"] = handler_manifest
    if business_term_manifest:
        payload["business_terms"] = business_term_manifest
    if table_manifest:
        payload["table_manifest"] = table_manifest
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False),
        },
    ]
    provider = llm_provider or build_llm_provider(settings)
    parsed, _ = provider.chat_json(messages, temperature=0, max_tokens=1200)
    return AnalysisPlan.model_validate(parsed)


def plan_analysis_with_rules(query: str, visible_catalog: Catalog) -> AnalysisPlan:
    lower = query.lower()
    table = visible_catalog.tables[0].name if visible_catalog.tables else "card_transaction"
    steps: list[AnalysisStep] = []
    assumptions = ["当前阶段只使用 metadata 和 synthetic mock 数据，不读取真实数据库。"]

    if ("状态" in query or "status" in lower) and any(token in query for token in ["多少笔", "几笔", "笔数", "数量", "次数"]):
        steps.append(
            AnalysisStep(
                operation="status_distribution",
                table=table,
                dimension="status",
                rationale="用户要求按交易状态统计记录笔数。",
                sql=f"SELECT status, COUNT(*) AS count FROM {table} GROUP BY status ORDER BY count DESC, status ASC",
            )
        )
    if "方差" in query or "variance" in lower:
        steps.append(
            AnalysisStep(
                operation="variance",
                table=table,
                metric="total_amount",
                time_field="transaction_at",
                rationale="用户要求计算波动/方差，使用交易金额进行总体方差计算。",
                sql=f"SELECT COUNT(*) AS count, AVG(total_amount) AS mean, AVG(total_amount * total_amount) - AVG(total_amount) * AVG(total_amount) AS variance FROM {table} WHERE total_amount IS NOT NULL",
            )
        )
    if "渠道" in query or "channel" in lower:
        steps.append(
            AnalysisStep(
                operation="top_n",
                table=table,
                metric="total_amount",
                group_by="card_channel",
                limit=10,
                rationale="按卡渠道聚合消费金额，观察渠道结构。",
                sql=f"SELECT card_channel, SUM(COALESCE(total_amount, 0)) AS total_amount FROM {table} GROUP BY card_channel ORDER BY total_amount DESC LIMIT 10",
            )
        )
    if "业务" in query or "分析" in query:
        steps.extend(
            [
                AnalysisStep(
                    operation="trend",
                    table=table,
                    metric="total_amount",
                    time_field="transaction_at",
                    grain="month",
                    rationale="观察金额随时间的趋势。",
                    sql=f"SELECT DATE_TRUNC('month', transaction_at) AS bucket, SUM(COALESCE(total_amount, 0)) AS total_amount FROM {table} GROUP BY bucket ORDER BY bucket ASC",
                ),
                AnalysisStep(
                    operation="status_distribution",
                    table=table,
                    dimension="status",
                    rationale="观察交易状态分布，辅助判断数据质量和业务完成情况。",
                    sql=f"SELECT status, COUNT(*) AS count FROM {table} GROUP BY status ORDER BY count DESC",
                ),
            ]
        )
    if not steps:
        steps.append(
            AnalysisStep(
                operation="top_n",
                table=table,
                metric="total_amount",
                group_by="account_id",
                limit=10,
                rationale="默认从客户消费金额 Top N 开始探索。",
                sql=f"SELECT account_id, SUM(COALESCE(total_amount, 0)) AS total_amount FROM {table} GROUP BY account_id ORDER BY total_amount DESC LIMIT 10",
            )
        )

    return AnalysisPlan(
        goal=query,
        assumptions=assumptions,
        steps=steps,
        required_metadata=sorted(
            {
                f"{step.table}.{field}"
                for step in steps
                for field in [step.metric, step.dimension, step.group_by, step.time_field]
                if field
            }
        ),
    )
