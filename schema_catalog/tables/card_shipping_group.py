"""自动提取的 card_shipping_group 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="card_shipping_group", description="")
class CardShippingGroup:
    COLUMNS = {
        "account_id": {"type": "uuid"},
        "group_id": {"type": "text", "description": "邮寄组id"},
        "balance_id": {"type": "uuid", "nullable": False, "description": "钱包id"},
        "budget_id": {"type": "uuid", "description": "预算id"},
        "fee": {"type": "numeric", "description": "物流交易费用"},
        "used_count": {"type": "numeric", "nullable": False, "description": "被使用的次数"},
        "expired_time": {"type": "text", "description": "group 资源过期时间（）"},
        "used": {"type": "text", "nullable": False, "description": "是否被使用"},
        "settled": {"type": "text", "nullable": False, "description": "是否已经结算"},
        "raw": {"type": "json"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
