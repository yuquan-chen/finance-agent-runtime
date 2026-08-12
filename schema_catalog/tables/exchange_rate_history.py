"""自动提取的 exchange_rate_history 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="exchange_rate_history", description="")
class ExchangeRateHistory:
    COLUMNS = {
        "ccy_from": {"type": "varchar", "nullable": False, "description": "被转换货币"},
        "ccy_to": {"type": "varchar", "nullable": False, "description": "目标货币"},
        "price": {"type": "varchar", "nullable": False, "description": "汇率值"},
        "platform": {"type": "varchar", "description": "数据源平台"},
        "ts": {"type": "varchar", "nullable": False, "description": "数据时间戳"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
