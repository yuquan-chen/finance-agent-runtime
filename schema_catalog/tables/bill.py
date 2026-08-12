"""自动提取的 bill 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="bill", description="")
class Bill:
    COLUMNS = {
        "account_id": {"type": "uuid", "description": "账户id"},
        "startTime": {"type": "timestamptz", "description": "申请月份起始"},
        "endTime": {"type": "timestamptz", "description": "申请月份结束"},
        "url": {"type": "text", "description": "下载链接"},
        "status": {"type": "varchar", "description": "下载链接"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
