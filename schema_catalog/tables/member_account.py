"""自动提取的 member_account 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="member_account", description="")
class MemberAccount:
    COLUMNS = {
        "account_id": {"type": "uuid", "description": "客户id"},
        "level_id": {"type": "uuid", "description": "等级id"},
        "level_type": {"type": "varchar", "nullable": False, "description": "会员类型"},
        "order_id": {"type": "uuid", "description": "当前会员对应订单id，基础会员时为空"},
        "start_time": {"type": "timestamptz", "nullable": False, "description": "开始时间"},
        "end_time": {"type": "timestamptz", "nullable": False, "description": "结束时间"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
