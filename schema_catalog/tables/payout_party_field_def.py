"""自动提取的 payout_party_field_def 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="payout_party_field_def", description="")
class PayoutPartyFieldDef:
    COLUMNS = {
        "key": {"type": "varchar", "description": "如 receiver_mobile"},
        "party": {"type": "varchar", "description": "sender 或 receiver"},
        "channel": {"type": "varchar", "description": "关联渠道，如 va_009"},
        "storage_target": {"type": "varchar", "description": "补采值存储位置"},
        "type": {"type": "varchar", "description": "text / select / date / file"},
        "value_format": {"type": "varchar", "description": "save 侧 plain / phone / date"},
        "catalogue": {"type": "varchar"},
        "validation_rule": {"type": "json"},
        "channel_field_names": {"type": "json"},
        "order": {"type": "text", "description": "表单 field_order，升序"},
        "enabled": {"type": "boolean"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
