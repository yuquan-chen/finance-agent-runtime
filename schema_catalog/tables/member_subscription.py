"""自动提取的 member_subscription 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="member_subscription", description="")
class MemberSubscription:
    COLUMNS = {
        "account_id": {"type": "uuid", "description": "客户id"},
        "level_id": {"type": "uuid", "description": "等级id"},
        "platform": {"type": "varchar", "description": "平台"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
