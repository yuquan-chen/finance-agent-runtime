"""自动提取的 activity_rule 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="activity_rule", description="")
class ActivityRule:
    COLUMNS = {
        "type": {"type": "varchar", "nullable": False, "description": "活动类型"},
        "name": {"type": "varchar", "nullable": False, "description": "活动名称"},
        "summary": {"type": "varchar", "description": "活动简介"},
        "description_arr": {"type": "json", "description": "活动描述, 数组"},
        "rule_json": {"type": "json", "description": "活动门槛"},
        "status": {"type": "varchar", "description": "状态"},
        "day_start_ts_s": {"type": "text", "description": "每个周期开始时间(从00:00开始计算,秒级,最大值86400)"},
        "event_duration_s": {"type": "text", "description": "每个周期持续时间(秒级)"},
        "start_date_at": {"type": "timestamptz", "description": "开始时间"},
        "end_date_at": {"type": "timestamptz", "description": "结束时间"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
