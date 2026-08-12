"""自动提取的 person_acquiring_record 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="person_acquiring_record", description="")
class PersonAcquiringRecord:
    COLUMNS = {
        "account_id": {"type": "uuid", "nullable": False, "description": "账户id"},
        "type": {"type": "varchar", "description": "收单方式"},
        "currency": {"type": "varchar", "description": "收单币种"},
        "payer_name": {"type": "varchar", "description": "收单联系人名称"},
        "payer_email": {"type": "varchar", "description": "收单联系人邮箱"},
        "person_acquiring_contact_id": {"type": "uuid", "description": "联系人id"},
        "product_name": {"type": "varchar", "description": "收单产品名称"},
        "description": {"type": "varchar", "description": "描述"},
        "pay_transaction_id": {"type": "uuid", "description": "交易id"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
