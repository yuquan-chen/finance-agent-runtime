"""自动提取的 card 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="card", description="")
class Card:
    COLUMNS = {
        "id_no": {"type": "bigint"},
        "account_id": {"type": "uuid", "description": "账户id"},
        "balance_id": {"type": "uuid", "description": "钱包id"},
        "budget_id": {"type": "uuid", "description": "预算id"},
        "call_id": {"type": "varchar", "description": "API客户的请求ID"},
        "label": {"type": "text", "description": "卡标签"},
        "currency": {"type": "varchar", "description": "币种"},
        "last4": {"type": "text", "description": "卡号后4位"},
        "first8": {"type": "text", "description": "卡号前8位"},
        "status": {"type": "varchar", "description": "卡状态"},
        "velocity_limit_window": {"type": "varchar", "description": "限额类型"},
        "velocity_amount_limit": {"type": "numeric", "description": "限额金额"},
        "channel_id": {"type": "varchar", "description": "card_channel_id"},
        "type": {"type": "varchar", "description": "卡类型，虚拟卡|实体卡"},
        "channel_balance": {"type": "numeric", "description": "渠道方余额"},
        "card_channel": {"type": "varchar", "description": "卡渠道"},
        "channel_card_id": {"type": "text", "description": "渠道卡id / token"},
        "card_holder_id": {"type": "text", "description": "持有人ID"},
        "raw": {"type": "json", "description": "三方开卡返回的原始数据"},
        "first_name": {"type": "varchar", "description": "持卡人的名"},
        "last_name": {"type": "varchar", "description": "持卡人的姓"},
        "card_address": {"type": "json", "description": "卡验证地址"},
        "physical_status": {"type": "varchar", "description": "卡状态"},
        "card_design_id": {"type": "uuid", "description": "卡设计Id"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
