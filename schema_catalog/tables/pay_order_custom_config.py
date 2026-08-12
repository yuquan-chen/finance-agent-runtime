"""自动提取的 pay_order_custom_config 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="pay_order_custom_config", description="暂未用到，未建表")
class PayOrderCustomConfig:
    COLUMNS = {
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
