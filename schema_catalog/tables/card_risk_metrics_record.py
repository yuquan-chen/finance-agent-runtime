"""自动提取的 card_risk_metrics_record 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="card_risk_metrics_record", description="")
class CardRiskMetricsRecord:
    COLUMNS = {
        "account_id": {"type": "uuid"},
        "card_id": {"type": "uuid"},
        "risk_level": {"type": "text", "description": "风险等级"},
        "card_channel": {"type": "varchar", "description": "卡渠道"},
        "amount": {"type": "numeric", "description": "此记录当时消费总金额usd"},
        "decline_amount": {"type": "numeric", "description": "此记录当时拒付总金额usd"},
        "count": {"type": "text", "description": "此记录卡渠道交易总笔数"},
        "decline_count": {"type": "text", "description": "此记录当时拒付总笔数"},
        "card_transaction_id": {"type": "uuid", "description": "卡交易表ID"},
        "is_reset": {"type": "text", "description": "是否已重置"},
        "reset_time": {"type": "timestamptz", "description": "重置时间"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
