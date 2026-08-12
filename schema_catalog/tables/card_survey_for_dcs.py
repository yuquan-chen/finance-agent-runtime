"""自动提取的 card_survey_for_dcs 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="card_survey_for_dcs", description="")
class CardSurveyForDcs:
    COLUMNS = {
        "account_id": {"type": "uuid", "nullable": False, "description": "账户id"},
        "status": {"type": "varchar", "description": "状态"},
        "phone_country_code": {"type": "varchar", "description": "手机所在国家"},
        "phone_area_code": {"type": "varchar", "description": "手机区号"},
        "phone_number": {"type": "varchar", "description": "手机号码,不带区号"},
        "employment_status": {"type": "varchar", "description": "工作状态"},
        "employer_name": {"type": "varchar", "description": "就业公司名称"},
        "employment_job_industry": {"type": "varchar", "description": "就业行业"},
        "occupation": {"type": "varchar", "description": "职业"},
        "job_seniority": {"type": "varchar", "description": "就业资历"},
        "purpose_of_account": {"type": "varchar", "description": "开户目的"},
        "source_of_funds": {"type": "varchar", "description": "资金来源"},
        "source_of_funds_country": {"type": "varchar", "description": "资金来源的国家"},
        "source_of_wealth": {"type": "varchar", "description": "财富来源"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
