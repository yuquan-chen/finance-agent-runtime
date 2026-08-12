"""自动提取的 rbac_api 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="rbac_api", description="")
class RbacApi:
    COLUMNS = {
        "name": {"type": "varchar", "description": "接口名称"},
        "path": {"type": "varchar", "description": "接口地址"},
        "methods": {"type": "varchar", "description": "请求方法"},
        "description": {"type": "varchar", "description": "接口描述"},
        "is_check": {"type": "text", "description": "是否检查权限"},
        "is_admin": {"type": "text", "description": "是否管理员接口"},
        "hash": {"type": "varchar", "description": "hash"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
