"""自动提取的 payout_method_locale 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="payout_method_locale", description="付款方式多语言条目：同一 {@link PayoutMethod} 下按 lang × field_key 唯一， 用于渠道标题 / 到账时效 / 描述 / 备注等展示（详见 {@link PayoutMethodFieldKeyEnum}）。")
class PayoutMethodLocale:
    COLUMNS = {
        "payout_method_id": {"type": "uuid", "nullable": False, "description": "payout_method.id"},
        "lang": {"type": "varchar", "nullable": False, "description": "语言 LangEnum"},
        "field_key": {"type": "varchar", "nullable": False, "description": "channel_title | arrival_time | description | remark 等"},
        "content": {"type": "text", "nullable": False, "description": "展示文案；remark 等可选字段可为空字符串"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
