"""自动提取的 kyt_record_pub 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="kyt_record_pub", description="")
class KytRecordPub:
    COLUMNS = {
        "address": {"type": "varchar", "description": "要查询的钱包地址"},
        "platform": {"type": "varchar", "description": "kyt平台"},
        "status": {"type": "varchar", "description": "状态"},
        "sub_status": {"type": "varchar", "description": "子状态"},
        "score": {"type": "varchar", "description": "kyt分数"},
        "raw": {"type": "json", "description": "kyt原始结果"},
        "pay_transaction_id": {"type": "uuid", "description": "支付交易id"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
