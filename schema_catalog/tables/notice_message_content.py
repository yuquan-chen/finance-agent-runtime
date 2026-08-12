"""自动提取的 notice_message_content 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="notice_message_content", description="")
class NoticeMessageContent:
    COLUMNS = {
        "message_id": {"type": "uuid", "description": " 消息id"},
        "language": {"type": "varchar", "description": "标题"},
        "title": {"type": "varchar", "description": "标题"},
        "content": {"type": "text", "description": "内容"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
