"""自动提取的 account_extend 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="account_extend", description="")
class AccountExtend:
    COLUMNS = {
        "account_id": {"type": "uuid"},
        "is_ota": {"type": "boolean", "description": "是否是OTA客户"},
        "channel_002_available": {"type": "boolean", "description": "002渠道可用"},
        "channel_004_available": {"type": "boolean", "description": "004渠道可用"},
        "channel_005_available": {"type": "boolean", "description": "005渠道可用"},
        "pay_available": {"type": "boolean", "description": "收单是否可用"},
        "physical_available": {"type": "boolean", "description": "物理卡是否可用"},
        "pay_settlement_cycle": {"type": "numeric", "description": "收单结算周期（天）"},
        "permissions": {"type": "jsonb", "description": "权限"},
        "biometrics_va": {"type": "jsonb", "description": "va005客户开户关联人员认证结果"},
        "social_info": {"type": "jsonb", "description": "社交信息"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
