"""自动提取的 card_order 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="card_order", description="")
class CardOrder:
    COLUMNS = {
        "account_id": {"type": "uuid", "description": "账户id"},
        "card_channel_type": {"type": "varchar", "description": "卡渠道类型"},
        "type": {"type": "varchar", "description": "开卡类型"},
        "status": {"type": "varchar", "description": "状态"},
        "card_id": {"type": "varchar", "description": "卡ID"},
        "order_num": {"type": "varchar", "description": "订单号"},
        "failed_code": {"type": "varchar", "description": "失败code"},
        "trace_request_id": {"type": "varchar", "description": "排查用request id"},
        "refund_transaction_id": {"type": "uuid", "description": "失败退款交易id"},
        "relation_transaction_ids": {"type": "varchar", "description": "关联交易ids, 逗号隔开"},
        "req_json": {"type": "jsonb", "description": "下单时的传参"},
        "next_json": {"type": "jsonb", "description": "下一步要用的参数"},
        "source_id": {"type": "varchar", "description": "来源"},
        "batch_id": {"type": "uuid", "description": "批次id"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
