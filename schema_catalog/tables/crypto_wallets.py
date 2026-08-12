"""自动提取的 crypto_wallets 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="crypto_wallets", description="")
class CryptoWallets:
    COLUMNS = {
        "account_id": {"type": "uuid", "nullable": False},
        "nickname": {"type": "varchar"},
        "currency": {"type": "varchar", "nullable": False},
        "balance_id": {"type": "uuid", "nullable": False},
        "description": {"type": "varchar"},
        "master": {"type": "boolean"},
        "chain": {"type": "varchar"},
        "sort": {"type": "text"},
        "status": {"type": "varchar"},
        "call_id": {"type": "varchar", "description": "API调用方ID"},
        "channel": {"type": "varchar", "description": "加密钱包渠道"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
