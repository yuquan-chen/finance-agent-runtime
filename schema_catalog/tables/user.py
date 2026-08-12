"""自动提取的 user 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="user", description="")
class User:
    COLUMNS = {
        "first_name": {"type": "text", "description": "first_name"},
        "last_name": {"type": "text", "description": "last_name"},
        "nickname": {"type": "text", "description": "用户名称"},
        "account_id": {"type": "uuid", "description": "账户ID"},
        "area_code": {"type": "text", "description": "手机号前缀"},
        "phone": {"type": "text", "description": "手机号"},
        "email": {"type": "text", "description": "邮箱"},
        "password": {"type": "text", "description": "密码"},
        "type": {"type": "varchar", "description": "用户类型"},
        "status": {"type": "varchar"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
