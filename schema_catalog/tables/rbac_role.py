"""自动提取的 rbac_role 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="rbac_role", description="")
class RbacRole:
    COLUMNS = {
        "account_id": {"type": "uuid", "description": "账户ID"},
        "name": {"type": "varchar", "description": "角色名称"},
        "description": {"type": "varchar", "description": "角色描述"},
        "is_admin": {"type": "text", "description": "是否是admin菜单"},
        "is_super": {"type": "boolean"},
        "status": {"type": "varchar", "description": "角色状态"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
