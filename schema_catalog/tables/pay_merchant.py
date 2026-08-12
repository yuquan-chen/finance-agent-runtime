"""自动提取的 pay_merchant 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="pay_merchant", description="")
class PayMerchant:
    COLUMNS = {
        "account_id": {"type": "uuid", "description": "账户ID"},
        "name": {"type": "varchar", "description": "商户名称"},
        "registration_country": {"type": "varchar", "description": "商户注册国家"},
        "binance_sub_merchant_id": {"type": "varchar", "description": "币安商户子id"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
