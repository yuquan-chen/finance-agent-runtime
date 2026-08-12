"""自动提取的 channel_balance 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="channel_balance", description="")
class ChannelBalance:
    COLUMNS = {
        "source_id": {"type": "varchar", "description": "三方ID"},
        "channel": {"type": "varchar", "description": "渠道"},
        "currency": {"type": "varchar", "description": "币种"},
        "balance": {"type": "numeric", "description": "金额"},
        "direction": {"type": "text", "description": "资金方向，1加,0减钱"},
        "type": {"type": "varchar"},
        "transaction_at": {"type": "timestamptz", "description": "交易时间"},
        "raw": {"type": "json", "description": "缓存数据"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
