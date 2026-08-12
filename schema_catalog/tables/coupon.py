"""自动提取的 coupon 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="coupon", description="golang使用，勿动")
class Coupon:
    COLUMNS = {
        "account_id": {"type": "uuid", "nullable": False, "description": "账户id"},
        "transaction_id": {"type": "uuid", "nullable": False, "description": "交易id"},
        "status": {"type": "varchar", "nullable": False, "description": "优惠券状态"},
        "received_time": {"type": "timestamptz", "nullable": False, "description": "领取时间"},
        "validat_time": {"type": "timestamptz", "nullable": False, "description": "生效时间"},
        "used_time": {"type": "timestamptz", "nullable": False, "description": "使用时间"},
        "origin_amount": {"type": "numeric", "nullable": False, "description": "原始金额"},
        "origin_fee": {"type": "numeric", "nullable": False, "description": "原始手续费"},
        "amount": {"type": "numeric", "nullable": False, "description": "优惠券金额"},
        "fee": {"type": "numeric", "nullable": False, "description": "优惠券手续费"},
        "currency": {"type": "varchar", "nullable": False, "description": "币种"},
        "value": {"type": "numeric", "nullable": False, "description": "优惠券值"},
        "type": {"type": "varchar", "nullable": False, "description": "优惠券类型"},
        "business_type": {"type": "varchar", "nullable": False, "description": "优惠券业务类型"},
        "name": {"type": "varchar", "nullable": False, "description": "优惠券名称"},
        "account_type": {"type": "varchar", "nullable": False, "description": "账户类型"},
        "has_send_lark": {"type": "boolean", "nullable": False, "description": "是否发送飞书"},
        "name_en": {"type": "varchar", "nullable": False, "description": "优惠券英文名称"},
        "batch_id": {"type": "uuid", "nullable": False, "description": "优惠券批次id"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
