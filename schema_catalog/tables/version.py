"""自动提取的 version 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="version", description="")
class Version:
    COLUMNS = {
        "type": {"type": "varchar", "description": "app类型"},
        "lang": {"type": "varchar", "description": "语言"},
        "row_version": {"type": "varchar", "description": "版本号"},
        "title": {"type": "varchar", "description": "标题"},
        "content_json": {"type": "json", "description": "内容"},
        "download_url": {"type": "varchar", "description": "下载地址"},
        "status": {"type": "varchar", "description": "状态"},
        "force_update": {"type": "boolean", "description": "强制更新"},
        "version_main_id": {"type": "uuid", "description": "主版本id"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
