"""自动提取的 questionnaire 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="questionnaire", description="* 默认问卷 一般用于存放各个模块配置的问卷")
class Questionnaire:
    COLUMNS = {
        "source_id": {"type": "text", "description": "渠道问题id"},
        "source_type": {"type": "varchar", "description": "渠道类型"},
        "question": {"type": "json", "description": "题目"},
        "options": {"type": "json", "description": "选项"},
        "is_multiple": {"type": "boolean", "description": "是否多选"},
        "type": {"type": "varchar", "description": "问题类型"},
        "enabled": {"type": "boolean", "description": "是否启用"},
        "order": {"type": "integer", "description": "排序"},
        "annex_configure": {"type": "json", "description": "文件配置"},
        "parent_source_id": {"type": "varchar", "description": "父级问题id"},
        "parent_source_option": {"type": "json", "description": "父级问题选项(父级别)"},
        "map_options": {"type": "varchar", "description": "映射的选项"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
