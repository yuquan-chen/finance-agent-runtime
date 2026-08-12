"""自动提取的 card_shipping_order 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="card_shipping_order", description="")
class CardShippingOrder:
    COLUMNS = {
        "account_id": {"type": "uuid"},
        "group_id": {"type": "text", "description": "邮寄组id"},
        "card_id": {"type": "text", "description": "卡id"},
        "fee": {"type": "numeric", "description": "物流交易费用"},
        "status": {"type": "text", "nullable": False, "description": "标准状态"},
        "raw": {"type": "json"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
