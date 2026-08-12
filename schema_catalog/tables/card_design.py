"""自动提取的 card_design 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="card_design", description="")
class CardDesign:
    COLUMNS = {
        "code": {"type": "varchar", "description": "识别码（业务标识，唯一）"},
        "cover_image_url": {"type": "varchar", "description": "卡封面图片地址"},
        "font_color": {"type": "varchar", "description": "字体颜色, 如 白色：#ffffff, 黑色：#000000"},
        "background_color": {"type": "varchar", "description": "背景颜色, 如：#000000"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
