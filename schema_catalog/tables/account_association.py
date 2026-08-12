"""自动提取的 account_association 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="account_association", description="")
class AccountAssociation:
    COLUMNS = {
        "account_id": {"type": "uuid", "description": "账户id"},
        "admin_user_id": {"type": "uuid", "description": "内部用户id-管理当前邀请码（例如销售）"},
        "am_id": {"type": "uuid", "description": "运营经理id"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
