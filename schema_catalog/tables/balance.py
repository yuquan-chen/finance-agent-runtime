"""自动提取的 balance 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="balance", description="")
class Balance:
    COLUMNS = {
        "account_id": {"type": "uuid"},
        "currency": {"type": "varchar", "description": "币种"},
        "available": {"type": "numeric", "description": "可用金额"},
        "pending": {"type": "numeric", "description": "处理中余额"},
        "frozen": {"type": "numeric", "description": "冻结中余额"},
        "type": {"type": "varchar", "description": "钱包类型"},
        "sub_type": {"type": "varchar", "description": "子类型, 具体的业务对应的钱包类型"},
        "business_id": {"type": "uuid", "description": "业务ID"},
        "group_id": {"type": "uuid", "description": "分组balance的ID"},
        "status": {"type": "varchar", "description": "状态"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
