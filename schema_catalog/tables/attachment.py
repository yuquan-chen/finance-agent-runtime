"""自动提取的 attachment 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="attachment", description="")
class Attachment:
    COLUMNS = {
        "source_id": {"type": "uuid", "description": "外部表id"},
        "source_type": {"type": "varchar", "description": "外部表名，如 cdd_person"},
        "attachment_type": {"type": "text", "description": "附件业务类型"},
        "account_id": {"type": "uuid", "description": "被操作账户的ID"},
        "filename": {"type": "text", "description": "文件名称"},
        "file_url": {"type": "text", "description": "文件url"},
        "file_urls": {"type": "json", "description": "文件url数组"},
        "file_use_type": {"type": "text", "description": "文件使用类型"},
        "file_type": {"type": "text", "description": "文件类型"},
        "media_id": {"type": "text", "description": "渠道方的文件ID"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
