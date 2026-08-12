"""自动提取的 account_config 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="account_config", description="")
class AccountConfig:
    COLUMNS = {
        "account_id": {"type": "uuid", "description": "账户id"},
        "status": {"type": "varchar", "description": "状态"},
        "type": {"type": "varchar", "description": "配置类型"},
        "condition": {"type": "varchar", "description": "条件"},
        "data_type": {"type": "varchar", "description": "数据"},
        "number": {"type": "numeric", "description": "数量"},
        "string": {"type": "varchar", "description": "字符串"},
        "json": {"type": "jsonb", "description": "json"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
