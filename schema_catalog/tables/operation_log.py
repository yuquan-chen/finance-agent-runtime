"""自动提取的 operation_log 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="operation_log", description="")
class OperationLog:
    COLUMNS = {
        "account_id": {"type": "uuid"},
        "user_am_id": {"type": "uuid", "description": "admin 或者 客户ID"},
        "source_id": {"type": "uuid"},
        "business_type": {"type": "varchar", "description": "业务类型"},
        "level": {"type": "varchar", "description": "日志级别"},
        "merchant_show": {"type": "boolean", "description": "是否商户端可见"},
        "pre_data": {"type": "json", "description": "修改前数据"},
        "new_data": {"type": "json", "description": "修改后数据"},
        "comment": {"type": "json", "description": "备注等"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
