"""自动提取的 crypto_payees 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="crypto_payees", description="")
class CryptoPayees:
    COLUMNS = {
        "payees_name": {"type": "varchar", "nullable": False},
        "account_id": {"type": "varchar", "nullable": False},
        "currency": {"type": "varchar", "nullable": False},
        "chain": {"type": "varchar", "nullable": False},
        "address": {"type": "varchar", "nullable": False},
        "payee_type": {"type": "varchar"},
        "wallet_id": {"type": "varchar"},
        "remarks": {"type": "varchar"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
