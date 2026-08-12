"""自动提取的 coupon_transaction_relation_record 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="coupon_transaction_relation_record", description="优惠券交易关联记录 仅用作记录，用于未核销时，回述交易是否真正被使用，不可他用")
class CouponTransactionRelationRecord:
    COLUMNS = {
        "account_id": {"type": "uuid", "nullable": False, "description": "账户id"},
        "coupon_id": {"type": "uuid", "nullable": False, "description": "优惠券id"},
        "transaction_id": {"type": "uuid", "nullable": False, "description": "交易id"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
