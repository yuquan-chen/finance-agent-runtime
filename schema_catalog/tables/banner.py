"""自动提取的 banner 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="banner", description="")
class Banner:
    COLUMNS = {
        "sort_order": {"type": "text", "nullable": False, "description": "排序值"},
        "name": {"type": "varchar", "nullable": False, "description": "名称"},
        "image_url": {"type": "varchar", "nullable": False, "description": "图片"},
        "platform": {"type": "varchar", "nullable": False, "description": "平台类型"},
        "business_type": {"type": "varchar", "nullable": False, "description": "业务类型"},
        "type": {"type": "varchar", "nullable": False, "description": "类型"},
        "status": {"type": "varchar", "description": "状态"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
