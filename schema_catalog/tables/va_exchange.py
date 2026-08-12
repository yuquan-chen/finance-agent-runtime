"""自动提取的 va_exchange 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="va_exchange", description="")
class VaExchange:
    COLUMNS = {
        "account_id": {"type": "uuid", "nullable": False, "description": "账户ID"},
        "payout_id": {"type": "uuid", "nullable": False, "description": "付款交易id"},
        "receive_type": {"type": "varchar", "nullable": False, "description": "付款方式"},
        "sell_currency": {"type": "varchar", "nullable": False, "description": "卖出币种"},
        "buy_currency": {"type": "varchar", "nullable": False, "description": "买入币种"},
        "sell_amount": {"type": "numeric", "nullable": False, "description": "卖出金额"},
        "buy_amount": {"type": "numeric", "nullable": False, "description": "买入金额"},
        "exchange_rate": {"type": "varchar", "nullable": False, "description": "汇率"},
        "fee_usd": {"type": "numeric", "nullable": False, "description": "手续费"},
        "rate_usd2sell": {"type": "varchar", "nullable": False, "description": "手续费汇率"},
        "channel_exchange_id": {"type": "varchar", "description": "渠道换汇id"},
        "channel_name": {"type": "varchar", "nullable": False, "description": "渠道名称"},
        "status": {"type": "varchar", "description": "状态"},
        "type": {"type": "varchar", "description": "类型"},
        "reason": {"type": "varchar", "description": "失败原因"},
        "raw": {"type": "json", "description": "原始json"},
        "channel_complete_at": {"type": "timestamptz", "description": "三方订单完成时间"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
