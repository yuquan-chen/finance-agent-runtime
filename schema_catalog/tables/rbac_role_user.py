"""自动提取的 rbac_role_user 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="rbac_role_user", description="")
class RbacRoleUser:
    COLUMNS = {
        "account_id": {"type": "uuid"},
        "user_id": {"type": "uuid"},
        "role_id": {"type": "uuid"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
