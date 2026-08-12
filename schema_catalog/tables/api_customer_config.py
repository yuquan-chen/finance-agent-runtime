"""自动提取的 api_customer_config 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="api_customer_config", description="* @deprecated")
class ApiCustomerConfig:
    COLUMNS = {
        "customer_id": {"type": "uuid"},
        "ip_whitelist": {"type": "json", "description": "白名单IP列表"},
        "webhook_list": {"type": "json", "description": "webhook 列表"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
