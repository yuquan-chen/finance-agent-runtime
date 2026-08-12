"""自动提取的 rbac_department 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="rbac_department", description="")
class RbacDepartment:
    COLUMNS = {
        "account_id": {"type": "uuid", "description": "账户ID"},
        "parent_department_id": {"type": "uuid", "description": "上级部门"},
        "name": {"type": "varchar", "description": "部门名称"},
        "description": {"type": "varchar", "description": "描述"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
