"""自动提取的 sys_transaction_clear 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="sys_transaction_clear", description="")
class SysTransactionClear:
    COLUMNS = {
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
