"""自动提取的 commission_type_analytics 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="commission_type_analytics", description="")
class CommissionTypeAnalytics:
    COLUMNS = {
        "account_id": {"type": "uuid", "description": "佣金获得者账号id"},
        "type": {"type": "varchar", "description": "佣金类型"},
        "total_commission": {"type": "numeric", "description": "累计佣金(已结算+未结算)"},
        "settled_commission": {"type": "numeric", "description": "已结算佣金"},
        "pending_commission": {"type": "numeric", "description": "未结算佣金"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
