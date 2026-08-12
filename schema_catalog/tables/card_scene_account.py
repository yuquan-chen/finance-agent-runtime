"""自动提取的 card_scene_account 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="card_scene_account", description="")
class CardSceneAccount:
    COLUMNS = {
        "account_id": {"type": "uuid"},
        "card_id": {"type": "uuid"},
        "config_id": {"type": "uuid", "description": "系统字段表ID"},
        "type": {"type": "text", "description": "匹配类型, 0-黑名单,1-白名单"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
