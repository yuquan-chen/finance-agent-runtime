"""自动提取的 account_kyt_balance 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="account_kyt_balance", description="")
class AccountKytBalance:
    COLUMNS = {
        "account_id": {"type": "uuid", "nullable": False, "description": "账户id"},
        "available": {"type": "text", "description": "可用次数"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
