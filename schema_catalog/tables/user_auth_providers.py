"""自动提取的 user_auth_providers 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="user_auth_providers", description="golang 表字段的创建时间，remarks version 之类的没有和node 统一。所以只能自己处理了")
class UserAuthProviders:
    COLUMNS = {
        "id": {"type": "text", "nullable": False, "description": "主键"},
        "user_id": {"type": "uuid"},
        "provider": {"type": "varchar", "description": "provider"},
        "email": {"type": "varchar", "description": "email"},
        "account_type": {"type": "varchar", "description": "account_type"},
        "created_at": {"type": "timestamptz"},
        "updated_at": {"type": "timestamptz"},
        "deleted_at": {"type": "timestamptz"},
    }
