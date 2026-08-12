"""自动提取的 crypto_addresses 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="crypto_addresses", description="")
class CryptoAddresses:
    COLUMNS = {
        "account_id": {"type": "uuid", "nullable": False},
        "wallet_id": {"type": "uuid", "nullable": False},
        "currency": {"type": "varchar", "nullable": False},
        "address": {"type": "varchar", "nullable": False},
        "chain": {"type": "varchar", "nullable": False},
        "address_tag": {"type": "varchar"},
        "remarks": {"type": "varchar"},
        "status": {"type": "varchar"},
        "platform": {"type": "varchar"},
        "account_key": {"type": "varchar"},
        "channel": {"type": "varchar", "description": "加密钱包渠道"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
