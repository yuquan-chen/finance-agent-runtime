"""自动提取的 budget_transaction 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="budget_transaction", description="")
class BudgetTransaction:
    COLUMNS = {
        "account_id": {"type": "uuid"},
        "card_id": {"type": "uuid"},
        "budget_id": {"type": "uuid", "nullable": False},
        "amount": {"type": "numeric", "description": "交易金额"},
        "fee": {"type": "numeric", "description": "手续费"},
        "type": {"type": "varchar", "description": "交易类型"},
        "status": {"type": "varchar", "description": "交易状态"},
        "currency": {"type": "varchar", "description": "币种"},
        "order_num": {"type": "text", "description": "订单号"},
        "transaction_id": {"type": "uuid", "description": "交易表ID"},
        "customer_notes": {"type": "varchar", "description": "客户备注(Notes)"},
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
