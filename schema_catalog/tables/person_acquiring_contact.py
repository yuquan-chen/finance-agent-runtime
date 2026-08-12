"""自动提取的 person_acquiring_contact 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="person_acquiring_contact", description="")
class PersonAcquiringContact:
    COLUMNS = {
        "account_id": {"type": "uuid", "nullable": False, "description": "账号"},
        "name": {"type": "varchar", "nullable": False, "description": "名称"},
        "email": {"type": "varchar", "nullable": False, "description": "邮箱"},
        "note": {"type": "varchar", "description": "备注"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
