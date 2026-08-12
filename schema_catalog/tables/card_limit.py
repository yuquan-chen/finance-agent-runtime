"""自动提取的 card_limit 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="card_limit", description="")
class CardLimit:
    COLUMNS = {
        "id_no": {"type": "bigint"},
        "account_id": {"type": "uuid", "description": "账户id"},
        "call_id": {"type": "varchar", "description": "API客户的请求ID"},
        "single_amount_limit": {"type": "numeric", "description": "单笔限额金额"},
        "day_amount_limit": {"type": "numeric", "description": "每天限额金额"},
        "week_amount_limit": {"type": "numeric", "description": "每周限额金额"},
        "month_amount_limit": {"type": "numeric", "description": "每月限额金额"},
        "quarter_amount_limit": {"type": "numeric", "description": "每季度限额金额"},
        "year_amount_limit": {"type": "numeric", "description": "每年限额金额"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
