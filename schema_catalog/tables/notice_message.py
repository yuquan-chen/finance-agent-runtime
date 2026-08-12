"""自动提取的 notice_message 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="notice_message", description="")
class NoticeMessage:
    COLUMNS = {
        "account_id": {"type": "uuid"},
        "user_id": {"type": "uuid", "description": "客户ID"},
        "type": {"type": "varchar", "description": "消息类型"},
        "is_read": {"type": "text", "description": "是否阅读"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
