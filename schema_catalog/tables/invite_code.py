"""自动提取的 invite_code 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="invite_code", description="")
class InviteCode:
    COLUMNS = {
        "account_id": {"type": "uuid", "description": "拥有者的账户id"},
        "user_id": {"type": "uuid", "description": "拥有者的用户id"},
        "admin_user_id": {"type": "uuid", "description": "内部用户id-管理当前邀请码（例如销售/运营）"},
        "code": {"type": "varchar", "description": "邀请码"},
        "type": {"type": "varchar", "description": "邀请码类型"},
        "use_type": {"type": "varchar", "description": "邀请码使用类型"},
        "use_comment": {"type": "varchar", "description": "邀请码使用备注"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
