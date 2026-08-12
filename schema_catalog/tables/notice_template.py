"""自动提取的 notice_template 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="notice_template", description="")
class NoticeTemplate:
    COLUMNS = {
        "name": {"type": "varchar", "description": "模板名称"},
        "params": {"type": "json", "description": "模板参数"},
        "enabled": {"type": "boolean", "description": "是否启用"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
