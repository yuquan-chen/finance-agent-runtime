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
1.1 你是唯一生成 SQL 模板的阶段。必须以 user_query（已合并且已脱值的目标）为准；你不会收到原始对话或真实参数值。
1.2 如果 action_context.base_query_reference 存在，它是同一会话中已执行查询的安全参考：根据当前 user_query 判断哪些历史约束仍然有效，再把当前请求的变化合并进去；必须重新生成 SQL 并重新查询，不能读取 prior result。relation=expand_detail 通常只把聚合/计数改为明细投影；relation=change_filter 或 change_time 时用当前明确的新条件覆盖同名旧条件；relation=sort 或 group 时只改变排序/分组。
1.2a 历史条件不是永久锁定：当前用户明确要求移除、替换或新增条件时，分别移除、覆盖或追加对应条件。用户没有提及的范围条件（例如原查询的时间范围、客户范围）默认保留；无法判断是否仍然有效时必须澄清。
1.2b 对 expand_detail，必须保留历史查询仍然有效的业务范围，但不能因为表名、业务术语或当前目标中的泛化名词自行新增过滤条件。例如“支付交易”可以用于选择 pay_transaction 表，但不能仅凭这个词新增 `type = 'payment'`。新的过滤条件必须来自当前用户明确表达并在 context.input_slots 中有对应槽位；没有槽位时不得写过滤字面量。
1.3 用户要求查看某个主体的交易/付款等明细记录（没有明确指定返回字段）时，使用主表别名的 ``SELECT p.*``，不要自行枚举列名；JOIN 的表只用于过滤时不选取其列。这样读取范围明确且不会猜测字段。
1.4 如果 action_context.revision=true，current_method_set 是当前待确认的方法集合：保持步骤编号和未被用户明确修改的步骤不变，只修改用户指明的步骤，并输出完整的方法集合。
1.5 如果 action_context.selected_capability_detail 存在，它是第一层已经由用户问题选中的受控能力。优先使用该 capability 作为主步骤 operation；不要把它替换成不相关的 operation。
2. 表名和字段名只能来自 context.visible_metadata；不要猜测或使用未展示的表/字段
3. 只写 SELECT，绝不写 INSERT/UPDATE/DELETE
4. 多表用 JOIN，关系参考 visible_metadata 中的 relationships
5. 业务术语参考 context.business_terms（如"消费"= type='consumption'）
6. 参数只能使用 context.input_slots 中提供的占位符。普通值使用 :input_N；范围值使用同一组的 :input_N_start 和 :input_N_end。绝不猜测、复述或写入任何真实筛选值；需要按值筛选时必须引用 input_slot，并遵守 slot 的 operator。必须根据 slot 的 type 和 semantic 选择兼容字段：公司名称等 text slot 应匹配名称字段，不能匹配 UUID/金额/日期字段；UUID slot 才能匹配 UUID 字段。
6.1 date/date_range slot 必须匹配时间字段。date_range 必须展开成闭区间起点和开区间终点，例如 `time_field >= :input_N_start AND time_field < :input_N_end`，不能写成 `time_field BETWEEN :input_N`，也不能把自然语言时间直接写进 SQL。
7. 文本字段的匹配必须根据用户意图选择：用户提供完整的主体名称或明确要求精确匹配时使用
   ``= :input_N``；用户只提供名称片段，或明确要求包含/模糊匹配时才使用
   ``ILIKE :input_N``。其他字段保持正确的类型比较，不能把 UUID/数值字段写成 ILIKE。

# 步骤设计原则
- 从宏观到微观：先看整体趋势，再拆维度
- 每个步骤解决一个问题，不要把多个分析塞进步骤
- 常见组合：状态分布 + 时间趋势 + 维度拆分
- 用户使用“分析”“概览”“健康度”或“从多个方面/维度”等综合分析表达时，必须输出至少 2 个互补步骤；如果目标包含状态，至少覆盖状态分布，并补充交易量或金额趋势等独立角度。这里的“比较”是比较本次分析的多个方法，不是引用多条历史查询。
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
                        "semantic_aliases": column.semantic_aliases,
                        "value_aliases": column.value_aliases,
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
    conversation_history: list[dict[str, Any]] | None = None,
    input_slots: list[dict[str, str]] | None = None,
) -> AnalysisPlan:
    payload: dict[str, Any] = {
        "user_query": query,
        "action_context": action_context or {},
        # SQL 规划器不接收原始对话；连续需求已在第一层合并为脱值 user_query。
        "conversation_history": [],
        "input_slots": input_slots or [],
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
