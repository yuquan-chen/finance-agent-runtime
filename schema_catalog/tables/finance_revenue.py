"""自动提取的 finance_revenue 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="finance_revenue", description="")
class FinanceRevenue:
    COLUMNS = {
        "related_system_table": {"type": "text", "description": "关联业务表"},
        "related_table_id": {"type": "text", "description": "关联业务表ID"},
        "total_incoming": {"type": "numeric", "description": "业务总收款(Gross Inflow)"},
        "total_outgoing": {"type": "numeric", "description": "业务总出款(Total Outflow)"},
        "net_revenue": {"type": "numeric", "description": "账面毛利 (total_incoming - total_outgoing)"},
        "external_cost": {"type": "numeric", "description": "外部硬性成本"},
        "currency": {"type": "text", "description": "本位币(通常统一为USD或CNY便于报表汇总)"},
        "accounting_subject": {"type": "text", "description": "会计科目: 如"},
        "settlement_status": {"type": "integer", "description": "结算状态: 0-未结算, 1-已对账, 2-已结转(已计入总账)"},
        "financial_period": {"type": "text", "description": "财务归属期 (如 2026-03-01, 用于月报分析)"},
        "reviewer_id": {"type": "integer", "description": "财务审核人ID"},
        "reviewed_at": {"type": "timestamptz", "description": "财务审核时间"},
        "accounting_remark": {"type": "text", "description": "财务专项备注"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
