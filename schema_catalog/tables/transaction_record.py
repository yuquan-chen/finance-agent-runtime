"""自动提取的 transaction_record 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="transaction_record", description="")
class TransactionRecord:
    COLUMNS = {
        "balance_available_amt": {"type": "numeric", "description": "源当前可用金额"},
        "balance_pending_amt": {"type": "numeric", "description": "源当前处理中金额"},
        "balance_frozen_amt": {"type": "numeric", "description": "源当前冻结金额"},
        "transaction_id": {"type": "uuid", "description": "大表交易id"},
        "account_id": {"type": "uuid"},
        "balance_id": {"type": "uuid"},
        "amount": {"type": "numeric", "description": "交易金额"},
        "fee": {"type": "numeric", "description": "交易手续费"},
        "type": {"type": "varchar", "description": "交易大类型"},
        "sub_type": {"type": "varchar", "description": "交易子类型"},
        "currency": {"type": "varchar", "description": "币种"},
        "status": {"type": "varchar", "description": "状态"},
        "operation_type": {"type": "varchar", "description": "操作类型"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
