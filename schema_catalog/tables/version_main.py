"""自动提取的 version_main 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="version_main", description="")
class VersionMain:
    COLUMNS = {
        "type": {"type": "varchar", "description": "app类型"},
        "title": {"type": "varchar", "description": "标题"},
        "row_version": {"type": "varchar", "description": "版本号"},
        "download_url": {"type": "varchar", "description": "下载地址"},
        "status": {"type": "varchar", "description": "状态"},
        "force_update": {"type": "boolean", "description": "强制更新"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
