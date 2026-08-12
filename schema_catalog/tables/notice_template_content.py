"""自动提取的 notice_template_content 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="notice_template_content", description="")
class NoticeTemplateContent:
    COLUMNS = {
        "template_id": {"type": "uuid", "description": "模板id"},
        "language": {"type": "varchar", "description": "模板语言"},
        "type": {"type": "varchar", "description": "模板类型"},
        "title": {"type": "varchar", "description": "标题"},
        "content": {"type": "jsonb", "description": "内容"},
        "enabled": {"type": "boolean", "description": "是否启用"},
        "masking": {"type": "boolean", "description": "是否脱敏处理"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
