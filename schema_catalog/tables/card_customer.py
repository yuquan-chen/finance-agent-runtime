"""自动提取的 card_customer 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="card_customer", description="")
class CardCustomer:
    COLUMNS = {
        "account_id": {"type": "uuid"},
        "customer_id": {"type": "uuid", "description": "客户ID, 如果是客户本身，则是客户自己，否则则是客户的客户"},
        "customer_type": {"type": "varchar", "description": "客户类型"},
        "business_name": {"type": "text", "description": "企业名称"},
        "business_registration_number": {"type": "text", "description": "企业注册号"},
        "registered_address": {"type": "json", "description": "企业注册地址"},
        "business_operation_address": {"type": "json", "description": "企业运营地址"},
        "channel": {"type": "varchar", "description": "渠道"},
        "type": {"type": "varchar", "description": "开户类型"},
        "status": {"type": "text", "description": "状态"},
        "channel_status": {"type": "varchar", "description": "开户状态"},
        "channel_id": {"type": "varchar", "description": "三方id"},
        "card_design_id": {"type": "varchar", "description": "卡面设计ID"},
        "raw": {"type": "json", "description": "原始数据"},
        "resRaw": {"type": "json", "description": "三方返回数据"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
