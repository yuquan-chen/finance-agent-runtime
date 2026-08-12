"""自动提取的 multi_lang 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="multi_lang", description="")
class MultiLang:
    COLUMNS = {
        "business_type": {"type": "varchar", "nullable": False, "description": "业务类型"},
        "lang": {"type": "varchar", "nullable": False, "description": "语言"},
        "field_key": {"type": "varchar", "nullable": False, "description": "字段"},
        "content": {"type": "varchar", "description": "翻译内容"},
        "content_arr": {"type": "json", "description": "翻译内容，数组格式"},
        "relation_id": {"type": "varchar", "nullable": False, "description": "关联id"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
