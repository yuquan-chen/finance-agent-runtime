"""自动提取的 card_holder 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="card_holder", description="")
class CardHolder:
    COLUMNS = {
        "account_id": {"type": "uuid"},
        "label": {"type": "text", "description": "标签"},
        "full_name": {"type": "text", "description": "名称拼接"},
        "full_name_reverse": {"type": "text", "description": "名称拼接反转"},
        "first_name": {"type": "text", "description": "first_name"},
        "last_name": {"type": "text", "description": "last_name"},
        "area_code": {"type": "text", "description": "手机号区号"},
        "phone": {"type": "text"},
        "email": {"type": "text"},
        "address": {"type": "json"},
        "use_scene": {"type": "varchar"},
        "call_id": {"type": "varchar", "description": "API客户的请求ID"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
