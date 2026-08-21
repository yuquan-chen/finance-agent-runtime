"""受控 Schema 选择器。

模型只会看到后端搜索出的少量表名和业务说明，不能看到全量字段，
更不能编造表名。字段和关系只会在选择后由 ``load_metadata`` 展开。
"""
from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from finance_agent.llm.provider import LlmProvider


class SchemaSelection(BaseModel):
    selected_tables: list[str] = Field(default_factory=list)
    reason: str = ""


SYSTEM_PROMPT = """你是金融数据 Agent 的 Schema 选择器。
你不写 SQL，不猜测字段，也不读取数据。

给定用户的脱敏分析目标、已选能力和后端搜索出的候选表目录，选择完成查询
所需要的最少表集合。只能从 candidate_tables 里的 name 中选择。
如果需要按公司/客户名称过滤交易，通常需要同时选择交易表和 account 表，
以便后续系统展开二者的真实字段和关系。

只输出 JSON：
{
  "selected_tables": ["候选表名"],
  "reason": "简短理由"
}
"""


def select_schema_with_llm(
    *,
    user_goal: str,
    capability_detail: dict[str, Any] | None,
    candidates: list[dict[str, str]],
    llm_provider: LlmProvider,
    repair_errors: list[str] | None = None,
) -> SchemaSelection:
    """让模型从受控候选目录中选择要展开的表。"""
    payload = {
        "user_goal": user_goal,
        "selected_capability": capability_detail or {},
        "candidate_tables": candidates,
        "repair_errors": repair_errors or [],
    }
    parsed, _ = llm_provider.chat_json(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        temperature=0,
        max_tokens=400,
    )
    selection = SchemaSelection.model_validate(parsed)
    allowed = {candidate["name"] for candidate in candidates}
    return selection.model_copy(
        update={"selected_tables": list(dict.fromkeys(name for name in selection.selected_tables if name in allowed))}
    )
