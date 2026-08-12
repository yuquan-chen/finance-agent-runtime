"""自动提取的 kyt_record 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="kyt_record", description="")
class KytRecord:
    COLUMNS = {
        "account_id": {"type": "uuid", "nullable": False, "description": "账户id"},
        "address": {"type": "varchar", "description": "钱包地址"},
        "platform": {"type": "varchar", "description": "kyt平台"},
        "status": {"type": "varchar", "description": "状态"},
        "sub_status": {"type": "varchar", "description": "子状态"},
        "score": {"type": "varchar", "description": "kyt分数"},
        "labels": {"type": "json", "description": "kyt labels"},
        "raw": {"type": "json", "description": "kyt原始结果"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
