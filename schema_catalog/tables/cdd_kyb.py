"""自动提取的 cdd_kyb 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="cdd_kyb", description="* kyb")
class CddKyb:
    COLUMNS = {
        "account_id": {"type": "uuid"},
        "ky_case_id": {"type": "uuid"},
        "type": {"type": "varchar", "description": "kyb类型"},
        "status": {"type": "varchar", "description": "kyc状态"},
        "is_last": {"type": "boolean", "description": "是否为最新数据"},
        "submit_time": {"type": "timestamptz", "description": "客户提交时间"},
        "review_time": {"type": "timestamptz", "description": "审核时间"},
        "close_time": {"type": "timestamptz", "description": "完结时间"},
        "review_result": {"type": "json", "description": "审核结果"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
