"""自动提取的 rbac_role_menu 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="rbac_role_menu", description="")
class RbacRoleMenu:
    COLUMNS = {
        "role_id": {"type": "uuid", "description": "角色ID"},
        "menu_id": {"type": "uuid", "description": "菜单ID"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
