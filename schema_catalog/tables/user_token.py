"""自动提取的 user_token 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="user_token", description="")
class UserToken:
    COLUMNS = {
        "account_id": {"type": "uuid"},
        "user_id": {"type": "uuid"},
        "token": {"type": "uuid"},
        "use_type": {"type": "varchar"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
