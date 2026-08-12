"""自动提取的 user_received_notice 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="user_received_notice", description="")
class UserReceivedNotice:
    COLUMNS = {
        "account_id": {"type": "uuid", "description": "账户ID"},
        "user_id": {"type": "uuid", "description": "用户ID"},
        "type": {"type": "varchar", "nullable": False, "description": "消息类型"},
        "subtype": {"type": "varchar", "nullable": False, "description": "子类型"},
        "subject": {"type": "varchar", "description": "主题"},
        "extraData": {"type": "json", "description": "定义保存的额外数据"},
        "html": {"type": "text", "description": "通知内容"},
        "is_read": {"type": "boolean", "description": "是否已读"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
