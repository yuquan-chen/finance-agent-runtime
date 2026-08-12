"""自动提取的 cdd_kyc 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="cdd_kyc", description="CustomerDueDiligence know-your-customer")
class CddKyc:
    COLUMNS = {
        "account_id": {"type": "uuid"},
        "ky_case_id": {"type": "uuid"},
        "type": {"type": "varchar", "description": "kyc类型"},
        "vendor": {"type": "varchar", "description": "CDD 对接厂商 sumsub/didit"},
        "status": {"type": "varchar", "description": "kyc状态"},
        "is_last": {"type": "boolean", "description": "是否为最新数据"},
        "submit_time": {"type": "timestamptz", "description": "客户提交时间"},
        "review_time": {"type": "timestamptz", "description": "审核时间"},
        "close_time": {"type": "timestamptz", "description": "完结时间"},
        "review_result": {"type": "json", "description": "审核结果"},
        "is_initial_review": {"type": "boolean", "description": "是否初审"},
        "initial_review_status": {"type": "varchar", "description": "初审结果"},
        "review_auditor_id": {"type": "uuid", "description": "初审人(user_id)"},
        "re_review_auditor_id": {"type": "uuid", "description": "复审人(user_id)"},
        "re_review_comment": {"type": "json", "description": "复审补充说明与附件"},
        "re_review_result": {"type": "json", "description": "复审结果"},
        "re_review_time": {"type": "timestamptz", "description": "复审时间"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
