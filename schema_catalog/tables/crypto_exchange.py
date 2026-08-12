"""自动提取的 crypto_exchange 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="crypto_exchange", description="")
class CryptoExchange:
    COLUMNS = {
        "base_currency": {"type": "varchar", "nullable": False},
        "quote_currency": {"type": "varchar", "nullable": False},
        "base_sz": {"type": "varchar", "nullable": False},
        "quote_sz": {"type": "varchar", "nullable": False},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
