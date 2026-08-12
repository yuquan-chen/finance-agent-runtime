"""自动提取的 hub 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="hub", description="")
class Hub:
    COLUMNS = {
        "name": {"type": "varchar", "description": "hub名称"},
        "logo": {"type": "varchar", "description": "hub logo"},
        "logo_black": {"type": "varchar", "description": "hub logo black"},
        "status": {"type": "varchar", "description": "hub状态"},
        "uri": {"type": "varchar", "description": "hub URI"},
        "operation_type": {"type": "varchar", "description": "hub 操作类型"},
        "i18n": {"type": "jsonb", "description": "hub 国际化数据"},
        "sort": {"type": "text", "description": "排序"},
        "sence": {"type": "varchar", "description": "场景"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
