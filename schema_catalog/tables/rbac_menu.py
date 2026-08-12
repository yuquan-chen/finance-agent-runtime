"""自动提取的 rbac_menu 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="rbac_menu", description="")
class RbacMenu:
    COLUMNS = {
        "name": {"type": "varchar", "description": "菜单名称"},
        "route_name": {"type": "varchar", "description": "对应得前端路由名称"},
        "parent_menu_id": {"type": "uuid", "description": "母菜单Id"},
        "description": {"type": "varchar", "description": "菜单描述"},
        "type": {"type": "varchar", "description": "菜单类型"},
        "is_display": {"type": "text", "description": "是否展示"},
        "route": {"type": "text", "description": "节点路由"},
        "is_admin": {"type": "text", "description": "是否是admin菜单"},
        "is_cache": {"type": "text", "description": "是否开启缓存"},
        "sort": {"type": "text", "description": "排序号，由小到大"},
        "icon": {"type": "text", "description": "对应的前端图标"},
        "group_key": {"type": "varchar", "description": "分组key"},
        "group_key_name": {"type": "varchar", "description": "分组名称"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
