"""自动提取的 commission_withdrawal_record 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="commission_withdrawal_record", description="")
class CommissionWithdrawalRecord:
    COLUMNS = {
        "account_id": {"type": "uuid", "description": "提现账户id"},
        "amount": {"type": "numeric", "description": "提现金额"},
        "fee": {"type": "numeric", "description": "提现手续费"},
        "type": {"type": "varchar", "nullable": False, "description": "提现类型"},
        "trx_id": {"type": "uuid", "description": "交易id"},
        "transaction_at": {"type": "timestamptz", "description": "订单创建时间"},
        "complete_at": {"type": "timestamptz", "description": "订单完成时间"},
        "batch_id": {"type": "varchar"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
