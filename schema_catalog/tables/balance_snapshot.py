"""自动提取的 balance_snapshot 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="balance_snapshot", description="")
class BalanceSnapshot:
    COLUMNS = {
        "snapshot_date": {"type": "varchar", "description": "快照时间，格式: 20250101"},
        "account_id": {"type": "uuid"},
        "currency": {"type": "varchar", "description": "币种"},
        "available": {"type": "numeric", "description": "可用金额"},
        "type": {"type": "varchar", "description": "钱包类型"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
