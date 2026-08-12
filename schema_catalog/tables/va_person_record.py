"""自动提取的 va_person_record 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="va_person_record", description="")
class VaPersonRecord:
    COLUMNS = {
        "account_id": {"type": "uuid", "description": "我方账户ID"},
        "channel_person_id": {"type": "varchar", "description": "渠道person.id"},
        "channel": {"type": "varchar", "description": "VA渠道"},
        "id_number": {"type": "varchar", "description": "证件号码"},
        "raw_data": {"type": "json", "description": "原始数据"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
