from __future__ import annotations

from typing import Any

from finance_agent.harness.plan_schema import Intent, QueryPlan


def render_answer(plan: QueryPlan, sql: str, rows: list[dict[str, Any]]) -> str:
    lines: list[str] = ["结论"]
    if plan.intent == Intent.count_distinct:
        count = rows[0].get("group_count") if rows else 0
        lines.append(f"查询完成，{plan.table} 中共有 {count} 个不同的 {plan.group_by}。")
    elif plan.intent == Intent.latest_by_group:
        lines.append(f"查询完成，已返回 {plan.table} 按 {plan.group_by} 分组后的最后一笔记录。")
        if rows:
            columns = list(rows[0].keys())
            lines.extend(["", "结果", "| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"])
            for row in rows[:50]:
                lines.append("| " + " | ".join(str(row.get(column, "")) for column in columns) + " |")
    elif plan.intent in {Intent.top_n, Intent.aggregate_by_group}:
        lines.append(f"查询完成，已返回 {plan.table} 的 {plan.intent.value} 结果。")
        lines.extend(["", "查询结果", "```json"])
        lines.append(str(rows))
        lines.append("```")
    else:
        lines.append("查询完成。")

    lines.extend(["", "SQL", "```sql", sql, "```"])
    return "\n".join(lines)
