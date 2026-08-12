"""自动提取的 invite_record 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="invite_record", description="")
class InviteRecord:
    COLUMNS = {
        "account_id": {"type": "uuid", "description": "绑定的账户id"},
        "invite_code_id": {"type": "uuid", "description": "邀请码id"},
        "use_comment": {"type": "varchar", "description": "途径说明"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
