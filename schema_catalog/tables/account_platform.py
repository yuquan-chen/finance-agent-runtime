"""自动提取的 account_platform 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="account_platform", description="* 账户支持的平台类型")
class AccountPlatform:
    COLUMNS = {
        "account_id": {"type": "uuid", "description": "账户id"},
        "platform": {"type": "varchar", "description": "平台"},
        "enabled": {"type": "boolean", "description": "是否启用"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
