"""自动提取的 balance_analytics 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="balance_analytics", description="余额统计")
class BalanceAnalytics:
    COLUMNS = {
        "account_id": {"type": "varchar", "nullable": False, "description": "账户id"},
        "total_available": {"type": "numeric", "description": "总价值"},
        "cw_available": {"type": "numeric", "description": "cw余额"},
        "va_available": {"type": "numeric", "description": "va余额"},
        "pay_available": {"type": "numeric", "description": "收单余额"},
        "card_available": {"type": "numeric", "description": "卡余额"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
