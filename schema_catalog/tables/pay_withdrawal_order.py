"""自动提取的 pay_withdrawal_order 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="pay_withdrawal_order", description="")
class PayWithdrawalOrder:
    COLUMNS = {
        "id_no": {"type": "bigint"},
        "account_id": {"type": "uuid", "nullable": False, "description": "提现账户id"},
        "fee": {"type": "numeric", "nullable": False, "description": "提现手续费"},
        "type": {"type": "varchar", "nullable": False, "description": "提现类型"},
        "currency": {"type": "varchar", "nullable": False, "description": "提现币种"},
        "to_wallet_id": {"type": "uuid", "nullable": False, "description": "提现到钱包"},
        "status": {"type": "varchar", "description": "交易状态"},
        "note": {"type": "varchar", "description": "备注"},
        "transaction_id": {"type": "uuid", "description": "关联的交易ID"},
        "crypto_transaction_id": {"type": "uuid", "description": "关联的加密钱包交易ID"},
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
