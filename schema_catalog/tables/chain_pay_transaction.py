"""自动提取的 chain_pay_transaction 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="chain_pay_transaction", description="")
class ChainPayTransaction:
    COLUMNS = {
        "pay_id_no": {"type": "bigint", "description": "pay_transaction的id_no"},
        "source_id": {"type": "varchar", "description": "来源ID"},
        "tx_hash": {"type": "varchar", "description": "交易hash"},
        "transfer_amount": {"type": "varchar", "description": "交易金额"},
        "type": {"type": "varchar", "description": "类型"},
        "exception_process_status": {"type": "varchar", "description": "异常订单处理状态"},
        "raw_data": {"type": "jsonb", "description": "原始数据"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
