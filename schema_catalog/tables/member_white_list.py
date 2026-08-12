"""自动提取的 member_white_list 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="member_white_list", description="")
class MemberWhiteList:
    COLUMNS = {
        "account_id": {"type": "uuid", "nullable": False, "description": "客户id"},
        "status": {"type": "varchar", "description": "状态"},
        "active_at": {"type": "timestamptz", "nullable": False, "description": "生效时间"},
        "operator_id": {"type": "uuid", "description": "操作人"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
