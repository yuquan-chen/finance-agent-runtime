"""自动提取的 hub_account 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="hub_account", description="")
class HubAccount:
    COLUMNS = {
        "hub_tag_id": {"type": "uuid", "description": "hub-tag id"},
        "hub_id": {"type": "varchar", "description": "hub logo"},
        "account_id": {"type": "uuid", "description": "账户id"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
