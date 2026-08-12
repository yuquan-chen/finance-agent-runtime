"""自动提取的 cdd_ky_case 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="cdd_ky_case", description="* CustomerDueDiligence case")
class CddKyCase:
    COLUMNS = {
        "account_id": {"type": "uuid"},
        "submit_time": {"type": "timestamptz", "description": "客户提交时间"},
        "review_time": {"type": "timestamptz", "description": "审核时间"},
        "call_id": {"type": "varchar", "description": "API Caller ID (unique within the same business)"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
