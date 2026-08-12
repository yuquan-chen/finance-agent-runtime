"""自动提取的 card_holder_channel 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="card_holder_channel", description="")
class CardHolderChannel:
    COLUMNS = {
        "account_id": {"type": "uuid"},
        "card_holder_id": {"type": "uuid"},
        "channel": {"type": "text"},
        "channel_id": {"type": "text"},
        "status": {"type": "text", "description": "状态"},
        "channel_status": {"type": "text"},
        "reason": {"type": "text"},
        "program_id": {"type": "text", "description": "渠道项目id(进一步划分渠道持卡人的属性)"},
        "raw": {"type": "json"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
