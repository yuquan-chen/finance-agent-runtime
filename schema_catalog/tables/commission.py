"""自动提取的 commission 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="commission", description="")
class Commission:
    COLUMNS = {
        "account_id": {"type": "uuid", "description": "用户账户id"},
        "settled_commission": {"type": "numeric", "description": "已结算佣金（单位：基础货币USD）"},
        "pending_commission": {"type": "numeric", "description": "待结算佣金（单位：基础货币USD）"},
        "withdrawn_commission": {"type": "numeric", "description": "已提现金额（单位：基础货币USD）"},
        "total_card_fees": {"type": "numeric", "description": "当前用户累计开卡费"},
        "total_va_account_fees": {"type": "numeric", "description": "当前用户累计开户费"},
        "total_transaction_fees": {"type": "numeric", "description": "当前用户累计交易手续费"},
        "total_crypto_exchange_fees": {"type": "numeric", "description": "当前用户累计承兑手续费"},
        "total_spent": {"type": "numeric", "description": "当前用户累计消费金额"},
        "level": {"type": "text", "description": "用户等级返佣等级体系"},
        "referral_count": {"type": "text", "description": "邀请人总数"},
        "activated_count": {"type": "text", "description": "已激活邀请人总数"},
        "activated": {"type": "boolean", "description": "是否激活(开户或开卡)"},
        "force": {"type": "boolean", "description": "是否强制设定等级用户，如果是，则不在更新其等级"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
