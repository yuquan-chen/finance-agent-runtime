"""自动提取的 notice_record_email 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="notice_record_email", description="")
class NoticeRecordEmail:
    COLUMNS = {
        "account_id": {"type": "uuid", "description": "账户ID"},
        "user_id": {"type": "uuid", "description": "用户ID"},
        "subject": {"type": "varchar", "description": "主题"},
        "email": {"type": "varchar", "description": "邮箱"},
        "html": {"type": "text", "description": "邮件内容"},
        "status": {"type": "varchar", "description": "是否发送成功"},
        "error_message": {"type": "text", "description": "错误原因"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
