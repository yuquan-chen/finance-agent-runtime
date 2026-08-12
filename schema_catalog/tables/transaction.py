"""自动提取的 transaction 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="transaction", description="")
class Transaction:
    COLUMNS = {
        "before_balance": {"type": "numeric", "description": "交易前金额"},
        "after_balance": {"type": "numeric", "description": "交易后金额"},
        "extra_data": {"type": "json", "description": "额外数据"},
        "transaction_at": {"type": "timestamptz", "description": "订单创建时间"},
        "relation_id": {"type": "uuid", "description": "关联订单id 如果为双边订单 则两个大表id一致"},
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
