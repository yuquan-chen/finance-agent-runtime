"""自动提取的 delivery_address 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="delivery_address", description="* 送货地址")
class DeliveryAddress:
    COLUMNS = {
        "account_id": {"type": "uuid", "description": "账户ID"},
        "first_name": {"type": "text", "description": "收件人first_name"},
        "last_name": {"type": "text", "description": "收件人last_name"},
        "area_code": {"type": "text", "description": "收件人手机号前缀"},
        "phone": {"type": "text", "description": "收件人手机号"},
        "country": {"type": "varchar", "description": "国家(英文名称,对应系统字典key,value_en)"},
        "country_code": {"type": "varchar", "description": "国家code"},
        "state": {"type": "varchar", "description": "州/省份"},
        "city": {"type": "varchar", "description": "城市"},
        "address_line1": {"type": "varchar", "description": "详细地址1"},
        "address_line2": {"type": "varchar", "description": "详细地址2"},
        "postal_code": {"type": "varchar", "description": "邮政编码"},
        "is_default": {"type": "boolean", "description": "是否为默认地址（未来可能有多个记录）"},
        "last_used_at": {"type": "timestamptz", "description": "最后使用时间"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
