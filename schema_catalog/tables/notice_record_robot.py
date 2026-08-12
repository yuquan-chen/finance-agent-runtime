"""自动提取的 notice_record_robot 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="notice_record_robot", description="")
class NoticeRecordRobot:
    COLUMNS = {
        "receive": {"type": "varchar", "description": "机器人key或者接收方"},
        "html": {"type": "text", "description": "内容"},
        "params": {"type": "json", "description": "内容"},
        "status": {"type": "varchar", "description": "是否发送成功"},
        "error_message": {"type": "text", "description": "错误原因"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
