"""自动提取的 member_black_list 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="member_black_list", description="")
class MemberBlackList:
    COLUMNS = {
        "account_id": {"type": "uuid", "nullable": False, "description": "客户id"},
        "status": {"type": "varchar", "description": "状态"},
        "operator_id": {"type": "uuid", "description": "操作人"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
