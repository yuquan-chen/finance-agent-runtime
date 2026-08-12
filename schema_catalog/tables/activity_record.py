"""自动提取的 activity_record 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="activity_record", description="")
class ActivityRecord:
    COLUMNS = {
        "type": {"type": "varchar", "description": "活动类型"},
        "event_code": {"type": "varchar", "description": "活动期数,如：251212"},
        "status": {"type": "varchar", "description": "状态"},
        "start_date_at": {"type": "timestamptz", "description": "开始时间"},
        "end_date_at": {"type": "timestamptz", "description": "结束时间"},
        "activity_rule_id": {"type": "uuid", "description": "父级活动规则id"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
