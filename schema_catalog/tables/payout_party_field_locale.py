"""自动提取的 payout_party_field_locale 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="payout_party_field_locale", description="")
class PayoutPartyFieldLocale:
    COLUMNS = {
        "key": {"type": "varchar", "description": "关联 field_def.key"},
        "lang": {"type": "varchar", "description": "语言 zh / en"},
        "label": {"type": "varchar"},
        "placeholder": {"type": "varchar"},
        "help_text": {"type": "varchar"},
        "remarks": {"type": "text"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
