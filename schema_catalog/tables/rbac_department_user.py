"""自动提取的 rbac_department_user 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="rbac_department_user", description="")
class RbacDepartmentUser:
    COLUMNS = {
        "account_id": {"type": "uuid", "description": "账户ID"},
        "user_id": {"type": "uuid"},
        "department_id": {"type": "uuid", "description": "部门ID"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
