"""自动提取的 crypto_withdrawal 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="crypto_withdrawal", description="")
class CryptoWithdrawal:
    COLUMNS = {
        "account_id": {"type": "varchar", "description": "账户id"},
        "chain": {"type": "varchar", "description": "链"},
        "currency": {"type": "varchar", "description": "币种"},
        "crypto_transaction_id": {"type": "uuid", "description": "关联的加密钱包交易ID"},
        "address": {"type": "varchar", "nullable": False},
        "status": {"type": "varchar"},
        "resJson": {"type": "json"},
        "channel": {"type": "varchar"},
        "transaction_at": {"type": "timestamptz", "description": "订单创建时间"},
        "completed_at": {"type": "timestamptz", "description": "订单完成时间"},
        "batch_id": {"type": "varchar"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
