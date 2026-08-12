"""自动提取的 va_transfer 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="va_transfer", description="")
class VaTransfer:
    COLUMNS = {
        "account_id": {"type": "uuid", "nullable": False, "description": "账户ID"},
        "business_type": {"type": "varchar", "nullable": False, "description": "业务类型"},
        "trx_id_from": {"type": "varchar", "nullable": False, "description": "出件交易ID"},
        "trx_id_to": {"type": "varchar", "nullable": False, "description": "进件交易ID"},
        "amount": {"type": "numeric", "description": "转账金额"},
        "currency": {"type": "varchar", "nullable": False, "description": "转账币种"},
        "channel": {"type": "varchar", "description": "渠道"},
        "channel_trx_id": {"type": "varchar", "description": "渠道订单ID"},
        "channel_order_no": {"type": "varchar", "description": "渠道订单号"},
        "reason": {"type": "varchar", "description": "失败原因"},
        "raw": {"type": "json", "description": "记录渠道输入输出"},
        "status": {"type": "varchar", "description": "交易状态"},
        "process_status": {"type": "varchar", "description": "流转态"},
        "review_time": {"type": "timestamptz", "description": "审核时间"},
        "complete_at": {"type": "timestamptz", "description": "订单完成时间"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
