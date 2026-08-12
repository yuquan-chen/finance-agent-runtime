"""自动提取的 airwallex_card_clear 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="airwallex_card_clear", description="")
class AirwallexCardClear:
    COLUMNS = {
        "channel_card_id": {"type": "text", "description": "渠道卡id"},
        "lifecycle_id": {"type": "text", "description": "生命周期id"},
        "is_cleared": {"type": "text", "description": "是否已清算"},
        "channel_clearing_time": {"type": "timestamptz", "description": "渠道清算时间"},
        "cleared_time": {"type": "timestamptz", "description": "清算时间"},
        "raw": {"type": "json", "description": "渠道清算原始信息"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
