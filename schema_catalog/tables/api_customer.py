"""自动提取的 api_customer 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="api_customer", description="")
class ApiCustomer:
    COLUMNS = {
        "account_id": {"type": "uuid"},
        "api_public_key": {"type": "text", "description": "加密公钥"},
        "status": {"type": "varchar"},
        "ip_whitelist": {"type": "json", "description": "白名单IP列表"},
        "auth_url": {"type": "varchar", "description": "认证url"},
        "enable_auth": {"type": "text", "description": "是否启用认证"},
        "enable_pri_encrypt": {"type": "text", "description": "是否启用私密信息加密"},
        "permissions": {"type": "json", "description": "权限列表"},
        "webhook_list": {"type": "json", "description": "webhook 列表"},
        "channel_004_mode": {"type": "varchar", "description": "004渠道接入模式"},
        "business_type": {"type": "varchar", "description": "适用业务"},
        "customer_type": {"type": "varchar", "description": "客户类型"},
        "inherit_parent_fees": {"type": "text", "description": "API二级账户费率缺省是否继承主账号后再落平台默认"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
