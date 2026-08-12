"""自动提取的 ledger_business_relation 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="ledger_business_relation", description="")
class LedgerBusinessRelation:
    COLUMNS = {
        "external_id": {"type": "varchar", "description": "换汇交易id"},
        "relation_id": {"type": "uuid", "description": "关联id"},
        "relation_table_name": {"type": "varchar", "description": "交易子状态"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
