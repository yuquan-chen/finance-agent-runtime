"""自动提取的 account_sales 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="account_sales", description="@deprecated 弃用 改为： account_association 表")
class AccountSales:
    COLUMNS = {
        "account_id": {"type": "uuid", "description": "账户id"},
        "sale_user_id": {"type": "uuid", "description": "销售ID"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
