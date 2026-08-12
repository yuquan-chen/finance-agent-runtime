"""自动提取的 crypto_webhook 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="crypto_webhook", description="")
class CryptoWebhook:
    COLUMNS = {
        "address": {"type": "varchar", "nullable": False},
        "data": {"type": "jsonb", "nullable": False},
        "source_id": {"type": "varchar", "nullable": False},
        "amount": {"type": "varchar", "nullable": False},
        "source_tx_id": {"type": "varchar", "nullable": False},
        "channel": {"type": "varchar", "nullable": False},
        "handler": {"type": "boolean"},
        "type": {"type": "varchar"},
        "error": {"type": "varchar"},
        "hash": {"type": "varchar"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
