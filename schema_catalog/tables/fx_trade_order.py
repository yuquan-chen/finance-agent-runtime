"""自动提取的 fx_trade_order 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="fx_trade_order", description="")
class FxTradeOrder:
    COLUMNS = {
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "order_no": {"type": "varchar", "description": "对客单编号"},
        "external_order_no": {"type": "varchar", "description": "外部系统单号"},
        "account_id": {"type": "uuid", "description": "用户id"},
        "order_status": {"type": "varchar", "description": "对客单状态 处理中、交易失败、待交割、交割成功、交割失败"},
        "business_type": {"type": "varchar", "description": "业务类型"},
        "channel_order_no": {"type": "varchar", "description": "渠道订单号，多个用逗号分隔"},
        "tenor": {"type": "varchar", "description": "tenor T0/T1/T2"},
        "ccy_pair": {"type": "varchar", "description": "货币对"},
        "sell_ccy": {"type": "varchar", "description": "卖出币种"},
        "buy_ccy": {"type": "varchar", "description": "买入币种"},
        "sell_amount": {"type": "varchar", "description": "卖出金额"},
        "buy_amount": {"type": "varchar", "description": "买入金额"},
        "side": {"type": "varchar", "description": "交易方向 sell/buy"},
        "rate": {"type": "varchar", "description": "汇率"},
        "settle_status": {"type": "varchar", "description": "平盘状态 待平盘、平盘中、已平盘 "},
        "quote_time": {"type": "varchar", "description": "询价时间"},
        "settle_time": {"type": "varchar", "description": "交割时间"},
        "error_msg": {"type": "varchar", "description": "错误信息"},
        "quote_id": {"type": "varchar", "description": "询价id"},
        "sell_account": {"type": "varchar", "description": "卖出币种钱包账户"},
        "buy_account": {"type": "varchar", "description": "买入币种钱包账户"},
        "customer_notes": {"type": "varchar", "description": "客户备注(Notes)"},
        "created_at": {"type": "timestamptz"},
        "updated_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
