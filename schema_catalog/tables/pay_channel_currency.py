"""自动提取的 pay_channel_currency 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="pay_channel_currency", description="")
class PayChannelCurrency:
    COLUMNS = {
        "pay_channel": {"type": "varchar", "description": "支付渠道"},
        "currency": {"type": "varchar", "description": "币种"},
        "chain": {"type": "varchar", "description": "币种支持的网络"},
        "channel_currency": {"type": "varchar", "description": "渠道支持的币种"},
        "channel_chain": {"type": "varchar", "description": "渠道支持的网络"},
        "channel_token_id": {"type": "varchar", "description": "渠道支持的token id"},
        "token_contract_address": {"type": "varchar", "description": "token合约地址"},
        "token_explorer_url": {"type": "varchar", "description": "token浏览器地址"},
        "status": {"type": "varchar", "description": "状态"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
