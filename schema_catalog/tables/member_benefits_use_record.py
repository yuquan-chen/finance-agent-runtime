"""自动提取的 member_benefits_use_record 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="member_benefits_use_record", description="")
class MemberBenefitsUseRecord:
    COLUMNS = {
        "account_id": {"type": "uuid", "nullable": False, "description": "客户id"},
        "type": {"type": "varchar", "nullable": False, "description": "类型"},
        "source_id": {"type": "uuid", "nullable": False, "description": "来源id"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
