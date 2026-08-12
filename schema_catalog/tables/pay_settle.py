"""自动提取的 pay_settle 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="pay_settle", description="")
class PaySettle:
    COLUMNS = {
        "id_no": {"type": "bigint"},
        "account_id": {"type": "uuid", "description": "账户ID"},
        "amount": {"type": "numeric", "description": "订单金额"},
        "fee": {"type": "numeric", "description": "交易手续费"},
        "status": {"type": "varchar", "description": "订单标准状态"},
        "balance_id": {"type": "uuid", "description": "关联的余额ID"},
        "transaction_id": {"type": "uuid", "description": "关联的交易ID"},
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
