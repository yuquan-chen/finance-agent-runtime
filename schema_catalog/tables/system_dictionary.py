"""自动提取的 system_dictionary 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="system_dictionary", description="")
class SystemDictionary:
    COLUMNS = {
        "type": {"type": "varchar", "description": "type"},
        "key": {"type": "varchar", "description": "key"},
        "value": {"type": "varchar", "description": "value"},
        "value_en": {"type": "varchar", "description": "value"},
        "raw": {"type": "jsonb", "description": "raw"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
