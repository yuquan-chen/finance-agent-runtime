"""自动提取的 api_webhook_log 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="api_webhook_log", description="")
class ApiWebhookLog:
    COLUMNS = {
        "account_id": {"type": "uuid"},
        "source_id": {"type": "uuid", "description": "源订单ID"},
        "type": {"type": "varchar", "description": "发送类型"},
        "status": {"type": "varchar", "description": "发送状态"},
        "send_url": {"type": "text", "description": "发送链接"},
        "send_count": {"type": "text", "description": "发送/重试次数"},
        "send_log": {"type": "json", "description": "发送与返回日志"},
        "send_data": {"type": "json", "description": "发送数据"},
        "request_id": {"type": "varchar", "description": "请求唯一标识"},
        "signature": {"type": "text", "description": "消息签名"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
