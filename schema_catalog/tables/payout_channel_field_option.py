"""自动提取的 payout_channel_field_option 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="payout_channel_field_option", description="")
class PayoutChannelFieldOption:
    COLUMNS = {
        "channel": {"type": "varchar", "description": "渠道，如 va_009"},
        "catalogue": {"type": "varchar", "description": "码表 REL/OCC 等"},
        "option_value": {"type": "varchar", "description": "渠道码值"},
        "lang": {"type": "varchar"},
        "label": {"type": "varchar"},
        "sort_order": {"type": "text"},
        "enabled": {"type": "boolean"},
        "remarks": {"type": "text"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
