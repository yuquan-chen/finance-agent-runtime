"""自动提取的 va_account 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="va_account", description="")
class VaAccount:
    COLUMNS = {
        "account_id": {"type": "uuid", "description": "账户ID"},
        "va_name": {"type": "text", "description": "客户自定义的银行账户名称"},
        "open_time": {"type": "timestamptz", "description": "开户时间"},
        "balance_id": {"type": "text", "description": "银行账户对应的钱包ID"},
        "channel_va_id": {"type": "text", "description": "渠道银行账户ID"},
        "channel_name": {"type": "varchar", "description": "渠道名称"},
        "currency": {"type": "varchar", "description": "银行账户币种"},
        "status": {"type": "varchar", "description": "银行账户状态"},
        "status_message": {"type": "varchar", "description": "银行账户状态消息"},
        "timeline": {"type": "json", "description": "时间线"},
        "deducted_free_quota": {"type": "numeric", "description": "扣减的免费额度"},
        "country": {"type": "varchar", "description": "开户国家/区域"},
        "bank_name": {"type": "varchar", "description": "开户行名称"},
        "payee_type": {"type": "varchar", "description": "账户收款类型"},
        "payee_currencies": {"type": "text", "description": "支持收款币种"},
        "trade_type": {"type": "varchar", "description": "贸易收款类型"},
        "apply_route_rule_id": {"type": "uuid", "description": "历史：va_apply_route_rule 主键"},
        "route_key": {"type": "varchar", "description": "稳定路由键 route_key"},
        "call_id": {"type": "varchar", "description": "API调用方ID"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
