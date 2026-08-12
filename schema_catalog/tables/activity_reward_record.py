"""自动提取的 activity_reward_record 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="activity_reward_record", description="")
class ActivityRewardRecord:
    COLUMNS = {
        "type": {"type": "varchar", "nullable": False, "description": "活动类型"},
        "sub_type": {"type": "varchar", "description": "子类型"},
        "account_id": {"type": "uuid", "description": "账户id"},
        "currency": {"type": "varchar", "description": "币种"},
        "amount": {"type": "numeric", "description": "金额"},
        "status": {"type": "varchar", "description": "状态"},
        "activity_rank_id": {"type": "uuid", "description": "活动排名id"},
        "activity_record_id": {"type": "uuid", "description": "父级活动记录id"},
        "activity_rule_id": {"type": "uuid", "description": "父级活动规则id"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
