"""自动提取的 version_feat_show 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="version_feat_show", description="")
class VersionFeatShow:
    COLUMNS = {
        "type": {"type": "varchar", "description": "app类型"},
        "row_version": {"type": "varchar", "description": "版本号"},
        "show_feat": {"type": "varchar", "nullable": False, "description": "隐藏的功能"},
        "is_show": {"type": "boolean", "description": "是否展示"},
        "account_id": {"type": "uuid", "description": "账户id"},
        "version_main_id": {"type": "uuid", "description": "主版本id"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
