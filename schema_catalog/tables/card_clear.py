"""自动提取的 card_clear 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="card_clear", description="")
class CardClear:
    COLUMNS = {
        "id_no": {"type": "bigint"},
        "account_id": {"type": "uuid"},
        "card_id": {"type": "uuid"},
        "channel_card_id": {"type": "text", "description": "渠道卡id"},
        "card_channel": {"type": "varchar", "description": "卡渠道"},
        "channel_update_time": {"type": "timestamptz", "description": "渠道更新时间"},
        "source_id": {"type": "text", "description": "原订单ID"},
        "card_transaction_id": {"type": "text", "description": "我方交易ID"},
        "transaction_type": {"type": "text", "description": "三方交易类型"},
        "is_cleared": {"type": "text", "description": "是否已清算"},
        "cleared_time": {"type": "timestamptz", "description": "清算时间"},
        "source_version": {"type": "integer", "description": "原订单版本号"},
        "raw": {"type": "json", "description": "原始数据"},
        "hash": {"type": "text", "description": "raw 的hash值"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
