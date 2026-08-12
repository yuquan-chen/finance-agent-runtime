"""自动提取的 banner_item 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="banner_item", description="")
class BannerItem:
    COLUMNS = {
        "sort_order": {"type": "text", "nullable": False, "description": "排序值"},
        "lang": {"type": "varchar", "nullable": False, "description": "语言"},
        "title": {"type": "varchar", "description": "标题"},
        "is_show_title": {"type": "boolean", "description": "是否显示标题"},
        "image_ur": {"type": "varchar", "description": "图片地址"},
        "jump_type": {"type": "varchar", "nullable": False, "description": "跳转方式"},
        "jump_url": {"type": "varchar", "description": "跳转地址"},
        "banner_id": {"type": "varchar", "nullable": False, "description": "banner id"},
        "group_id": {"type": "uuid", "description": "分组ID"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
