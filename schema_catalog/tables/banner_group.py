"""自动提取的 banner_group 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="banner_group", description="")
class BannerGroup:
    COLUMNS = {
        "name": {"type": "varchar", "nullable": False, "description": "分组名称"},
        "business_type": {"type": "varchar", "nullable": False, "description": "业务类型"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
