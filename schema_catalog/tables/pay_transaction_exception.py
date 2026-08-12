"""自动提取的 pay_transaction_exception 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="pay_transaction_exception", description="")
class PayTransactionException:
    COLUMNS = {
        "account_id": {"type": "uuid", "description": "账户ID"},
        "pay_transaction_id": {"type": "uuid", "description": "pay_transaction.id"},
        "exception_index": {"type": "text", "description": "同个pay_transaction_id下第几次异常数据，从0开始"},
        "pay_transaction_id_no": {"type": "bigint", "description": "pay_transaction.id_no"},
        "pay_channel": {"type": "varchar", "description": "支付渠道类型"},
        "call_id": {"type": "varchar", "description": "call_id"},
        "order_amount": {"type": "numeric", "description": "原订单金额"},
        "order_currency": {"type": "varchar", "description": "原订单币种"},
        "order_chain": {"type": "varchar", "description": "原订单链"},
        "actual_amount": {"type": "numeric", "description": "实际异常到账累计金额"},
        "actual_currency": {"type": "varchar", "description": "实际异常到账主币种"},
        "actual_chain": {"type": "varchar", "description": "实际异常到账主链"},
        "actual_payment_count": {"type": "text", "description": "实际异常付款次数"},
        "abnormal_tags": {"type": "jsonb", "description": "异常标签"},
        "status": {"type": "varchar", "description": "异常处理状态"},
        "sub_status": {"type": "varchar", "description": "异常处理二级状态"},
        "refunded_amount": {"type": "numeric", "description": "已退款金额"},
        "actual_payment_details": {"type": "jsonb", "description": "实际异常付款明细"},
        "raw_data": {"type": "jsonb", "description": "原始数据"},
        "fixed_at": {"type": "timestamptz", "description": "原订单修复时间"},
        "note": {"type": "text", "description": "备注"},
        "fix_error": {"type": "text", "description": "原订单修复错误"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
