"""自动提取的 va_channel_data 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="va_channel_data", description="* VA渠道交易数据表")
class VaChannelData:
    COLUMNS = {
        "account_id": {"type": "uuid", "description": "交易发起方account_id"},
        "channel_account_id": {"type": "varchar", "description": "渠道账户ID"},
        "request_id": {"type": "varchar", "description": "request_id"},
        "reference": {"type": "varchar", "description": "reference"},
        "origin_id": {"type": "varchar", "description": "渠道交易id"},
        "channel_name": {"type": "varchar", "description": "渠道名称"},
        "business_type": {"type": "varchar", "description": "业务类型"},
        "channel_type": {"type": "varchar", "description": "渠道交易类型"},
        "channel_created_at": {"type": "timestamptz", "description": "渠道创建时间"},
        "channel_completed_at": {"type": "timestamptz", "description": "渠道完成时间"},
        "amount": {"type": "numeric", "description": "渠道订单金额"},
        "currency": {"type": "varchar", "description": "渠道订单币种"},
        "raw": {"type": "json", "description": "渠道原始数据"},
        "hash": {"type": "varchar", "description": "raw的hash值"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
