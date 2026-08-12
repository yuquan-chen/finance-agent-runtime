"""自动提取的 va_inbound_limit 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="va_inbound_limit", description="")
class VaInboundLimit:
    COLUMNS = {
        "account_id": {"type": "uuid", "description": "账户ID"},
        "channel": {"type": "varchar", "description": "渠道"},
        "total": {"type": "numeric", "description": "累计额度"},
        "available": {"type": "numeric", "description": "可用额度"},
        "currency": {"type": "varchar", "description": "币种"},
        "type": {"type": "varchar", "description": "额度类型"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
