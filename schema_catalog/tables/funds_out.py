"""自动提取的 funds_out 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="funds_out", description="")
class FundsOut:
    COLUMNS = {
        "id_no": {"type": "bigint", "nullable": False, "description": "订单号"},
        "account_id": {"type": "uuid", "nullable": False, "description": "提现账户id"},
        "from_currency": {"type": "varchar", "nullable": False, "description": "兑换币种"},
        "to_currency": {"type": "varchar", "nullable": False, "description": "收到币种"},
        "fee_currency": {"type": "varchar", "nullable": False, "description": "手续费币种"},
        "from_balance_id": {"type": "uuid", "nullable": False, "description": "兑换来源balance"},
        "from_balance_type": {"type": "varchar", "description": "来源balance类型"},
        "business_type": {"type": "varchar", "description": "业务类型"},
        "external_id": {"type": "varchar", "description": "外部id"},
        "status": {"type": "varchar", "description": "交易状态"},
        "out_transaction_id": {"type": "uuid", "description": "出金关联的交易ID"},
        "out_trace_transaction_id": {"type": "uuid", "description": "出金追踪用的交易id, 如：加密钱包交易ID"},
        "fx_id": {"type": "varchar", "description": "换汇交易id"},
        "process_status": {"type": "varchar", "description": "交易子状态"},
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
