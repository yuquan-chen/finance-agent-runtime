"""自动提取的 activity_rank 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="activity_rank", description="")
class ActivityRank:
    COLUMNS = {
        "type": {"type": "varchar", "nullable": False, "description": "活动类型"},
        "account_id": {"type": "uuid", "description": "账户id"},
        "value": {"type": "numeric", "description": "排名值，用于确定用户在活动中的排名,如：开卡数，消费额"},
        "raw": {"type": "json", "description": "原始数据,证明某用户在某活动下的排名值"},
        "activity_record_id": {"type": "uuid", "description": "父级活动记录id"},
        "activity_rule_id": {"type": "uuid", "description": "父级活动规则id"},
        "is_above_threshold": {"type": "boolean", "description": "是否满足门槛"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
