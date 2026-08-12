"""自动提取的 kyt_top_up_record 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="kyt_top_up_record", description="")
class KytTopUpRecord:
    COLUMNS = {
        "account_id": {"type": "uuid", "nullable": False, "description": "账户id"},
        "status": {"type": "varchar", "description": "状态"},
        "count": {"type": "text", "description": "数量"},
        "pay_transaction_id": {"type": "varchar", "description": "收单id"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
