"""自动提取的 payout_payee_channel 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="payout_payee_channel", description="")
class PayoutPayeeChannel:
    COLUMNS = {
        "account_id": {"type": "uuid", "nullable": False, "description": "账户ID"},
        "payee_id": {"type": "uuid", "nullable": False, "description": "收款人ID"},
        "channel": {"type": "varchar", "description": "收款人渠道"},
        "channel_payee_id": {"type": "varchar", "description": "渠道收款人ID"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
