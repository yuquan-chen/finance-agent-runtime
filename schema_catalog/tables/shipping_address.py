"""自动提取的 shipping_address 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="shipping_address", description="")
class ShippingAddress:
    COLUMNS = {
        "account_id": {"type": "uuid", "description": "账户id"},
        "country_code": {"type": "varchar", "description": "国家码 ISO 2位 eg: CN/US/SG"},
        "first_name": {"type": "varchar", "description": "收货人名"},
        "last_name": {"type": "varchar", "description": "收货人姓"},
        "phone_area_code": {"type": "varchar", "description": "手机区号"},
        "phone_number": {"type": "varchar", "description": "手机号"},
        "state": {"type": "varchar", "description": "省/州"},
        "city": {"type": "varchar", "description": "市"},
        "postal_code": {"type": "varchar", "description": "邮编"},
        "address": {"type": "varchar", "description": "地址1"},
        "address2": {"type": "varchar", "description": "地址2"},
        "address3": {"type": "varchar", "description": "地址3"},
        "last_used_at": {"type": "timestamptz", "description": "最后一次使用时间"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
