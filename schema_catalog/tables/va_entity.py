"""自动提取的 va_entity 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="va_entity", description="")
class VaEntity:
    COLUMNS = {
        "account_id": {"type": "uuid", "description": "我方账户ID"},
        "va_entity_id": {"type": "varchar", "description": "渠道用户/进件ID"},
        "account_name_en": {"type": "varchar", "description": "企业英文名称"},
        "operating_address": {"type": "json", "description": "企业运营地址"},
        "raw_data": {"type": "json", "description": "原始数据"},
        "channel": {"type": "varchar", "description": "VA渠道"},
        "status": {"type": "varchar", "description": "我方进件状态"},
        "biometric_noticed": {"type": "boolean", "description": "是否已经通知关联人员生物特征认证"},
        "channel_status": {"type": "varchar", "description": "渠道审核状态"},
        "reason": {"type": "varchar", "description": "渠道审核失败等各种内部原因"},
        "final_review_at": {"type": "timestamptz", "description": "渠道最后审核时间"},
        "complete_at": {"type": "timestamptz", "description": "完成时间"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
