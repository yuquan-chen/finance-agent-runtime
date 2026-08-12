"""自动提取的 run_in_transaction 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="run_in_transaction", description="")
class RunInTransaction:
    COLUMNS = {
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
