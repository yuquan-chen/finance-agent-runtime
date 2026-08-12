"""自动提取的 payout_method 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="payout_method", description="付款方式主数据：一行对应一种 VA 付款渠道（005/006/007），子表 {@link PayoutMethodLocale} 存多语言说明文案。")
class PayoutMethod:
    COLUMNS = {
        "code": {"type": "varchar", "nullable": False, "description": "渠道编码，与 VAChannelNameEnum 一致"},
        "channel_name": {"type": "varchar", "nullable": False, "description": "展示用渠道名 zenus/gep/epay"},
        "sort_order": {"type": "text", "description": "展示顺序"},
        "enabled": {"type": "boolean", "description": "是否启用"},
        "pay_amount_gt": {"type": "numeric", "description": "付款金额下限 USD（须大于）"},
        "receive_amount_gt": {"type": "numeric", "description": "收款金额下限 USD（须大于）"},
        "icon_light": {"type": "varchar", "description": "白天模式图标 URL"},
        "icon_dark": {"type": "varchar", "description": "夜间模式图标 URL"},
        "supported_currencies_person": {"type": "jsonb", "description": "个人客户展示币种，如 ["},
        "supported_currencies_enterprise": {"type": "jsonb", "description": "企业客户展示币种（含 enterprise/self_employed），如 ["},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
