"""自动提取的 fcm_topic_config 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="fcm_topic_config", description="FCM topic 订阅配置（表 fcm_topic_config）")
class FcmTopicConfig:
    COLUMNS = {
        "resolver": {"type": "varchar", "description": "Resolver 标识，如 lang / kyc / card_bin"},
        "scope": {"type": "varchar", "description": "作用域：device | user"},
        "topic_prefix": {"type": "varchar", "description": "FCM topic 前缀（已含环境段；不含后缀取值）"},
        "enabled": {"type": "boolean", "description": "是否启用"},
        "title": {"type": "varchar", "description": "后台展示说明"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
