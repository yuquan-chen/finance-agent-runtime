"""自动提取的 va_inbound_order 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="va_inbound_order", description="VA入金额度订单")
class VaInboundOrder:
    COLUMNS = {
        "account_id": {"type": "uuid", "nullable": False, "description": "账户ID"},
        "channel": {"type": "varchar", "nullable": False, "description": "订单渠道"},
        "channel_order_id": {"type": "varchar", "description": "渠道订单编号"},
        "user_order_id": {"type": "varchar", "description": "用户订单编号"},
        "state": {"type": "varchar", "nullable": False, "description": "订单审核状态"},
        "req_json": {"type": "json", "description": "提交到渠道的json数据"},
        "res_json": {"type": "json", "description": "渠道对提交的相应结果"},
        "reason": {"type": "varchar", "description": "渠道审核失败等各种内部原因"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
