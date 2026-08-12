"""自动提取的 rbac_menu_api 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="rbac_menu_api", description="")
class RbacMenuApi:
    COLUMNS = {
        "menu_id": {"type": "uuid", "description": "菜单ID"},
        "api_id": {"type": "uuid", "description": "接口ID"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
