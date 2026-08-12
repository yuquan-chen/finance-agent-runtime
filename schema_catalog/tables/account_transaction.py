"""自动提取的 account_transaction 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="account_transaction", description="")
class AccountTransaction:
    COLUMNS = {
        "id_no": {"type": "bigint"},
        "account_id": {"type": "uuid"},
        "order_num": {"type": "text", "description": "订单号"},
        "balance_id": {"type": "uuid"},
        "source_id": {"type": "varchar", "description": "原始订单号"},
        "transaction_id": {"type": "uuid"},
        "card_id": {"type": "uuid", "description": "卡id"},
        "currency": {"type": "varchar", "description": "币种"},
        "transaction_currency": {"type": "varchar", "description": "原始交易币种"},
        "transaction_amount": {"type": "numeric", "description": "原始交易金额"},
        "fx_rate": {"type": "numeric", "description": "汇率"},
        "fee": {"type": "numeric", "description": "交易费用"},
        "amount": {"type": "numeric", "description": "订单结算金额"},
        "type": {"type": "varchar", "description": "业务类型"},
        "action": {"type": "varchar", "description": "交易动作"},
        "status": {"type": "varchar", "description": "交易状态"},
        "process_status": {"type": "varchar", "description": "流转态"},
        "tx_source": {"type": "text", "description": "交易来源"},
        "call_id": {"type": "varchar", "description": "API客户的请求ID"},
        "customer_notes": {"type": "varchar", "description": "客户备注(Notes)"},
        "reference": {"type": "varchar", "description": "附言"},
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
