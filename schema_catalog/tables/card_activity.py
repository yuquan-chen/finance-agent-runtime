"""自动提取的 card_activity 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="card_activity", description="")
class CardActivity:
    COLUMNS = {
        "name": {"type": "varchar", "description": "活动名称"},
        "card_channel_id": {"type": "uuid", "description": "渠道ID"},
        "card_function_type": {"type": "varchar", "description": "卡功能类型"},
        "create_card_fee": {"type": "varchar", "description": "开卡手续费"},
        "status": {"type": "varchar", "description": "状态"},
        "start_date_at": {"type": "timestamptz", "description": "开始时间"},
        "end_date_at": {"type": "timestamptz", "description": "结束时间"},
        "card_design_id": {"type": "uuid", "description": "卡设计ID"},
        "available_countries": {"type": "jsonb", "description": "活动可用国家，有值时优先使用"},
        "disable_countries": {"type": "jsonb", "description": "活动禁用国家"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
