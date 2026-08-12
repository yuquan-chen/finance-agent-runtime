"""自动提取的 card_kyc 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="card_kyc", description="")
class CardKyc:
    COLUMNS = {
        "account_id": {"type": "uuid", "nullable": False, "description": "账户id"},
        "card_channel_type": {"type": "varchar", "description": "卡渠道类型"},
        "level_name": {"type": "varchar", "description": "级别名称"},
        "external_user_id": {"type": "varchar", "description": "外部用户ID"},
        "applicant_id": {"type": "varchar", "description": "申请人ID"},
        "status": {"type": "varchar", "description": "状态"},
        "return_link": {"type": "varchar", "description": "返回link"},
        "card_channel_id": {"type": "varchar", "description": "请求时的卡渠道"},
        "reset_count": {"type": "bigint", "description": "重置kyc次数"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
