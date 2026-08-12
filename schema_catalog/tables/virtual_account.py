"""自动提取的 virtual_account 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="virtual_account", description="")
class VirtualAccount:
    COLUMNS = {
        "account_id": {"type": "varchar", "nullable": False},
        "account_type": {"type": "varchar", "nullable": False},
        "balance_id": {"type": "varchar", "nullable": False},
        "currency": {"type": "varchar", "nullable": False},
        "status": {"type": "varchar", "nullable": False},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
