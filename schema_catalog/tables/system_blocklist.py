"""自动提取的 system_blocklist 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="system_blocklist", description="")
class SystemBlocklist:
    COLUMNS = {
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "type": {"type": "varchar"},
        "value": {"type": "varchar"},
    }
