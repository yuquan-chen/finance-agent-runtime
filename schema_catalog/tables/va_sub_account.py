"""自动提取的 va_sub_account 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="va_sub_account", description="")
class VaSubAccount:
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
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
