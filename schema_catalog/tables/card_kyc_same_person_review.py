"""自动提取的 card_kyc_same_person_review 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="card_kyc_same_person_review", description="")
class CardKycSamePersonReview:
    COLUMNS = {
        "account_id": {"type": "uuid", "description": "账户id"},
        "card_kyc_id": {"type": "uuid", "description": "卡KYC id"},
        "main_kyc_id": {"type": "uuid", "description": "我方主KYC id"},
        "dcs_applicant_id": {"type": "varchar", "description": "DCS Sumsub applicant id"},
        "status": {"type": "varchar", "description": "状态"},
        "tags": {"type": "jsonb", "description": "审核标签"},
        "check_hash": {"type": "varchar", "description": "校对信息hash"},
        "check_info": {"type": "jsonb", "description": "校对信息快照"},
        "trigger_error_code": {"type": "integer", "description": "触发的错误码"},
        "review_user_id": {"type": "uuid", "description": "审核管理员id"},
        "review_at": {"type": "timestamptz", "description": "审核时间"},
        "review_comment": {"type": "jsonb", "description": "审核备注"},
        "expired_at": {"type": "timestamptz", "description": "过期时间"},
        "expire_reason": {"type": "varchar", "description": "过期原因"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
