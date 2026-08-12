"""自动提取的 payout_sender_profile 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="payout_sender_profile", description="")
class PayoutSenderProfile:
    COLUMNS = {
        "account_id": {"type": "uuid", "nullable": False, "description": "平台账户 ID，唯一"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
