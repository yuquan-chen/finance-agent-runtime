"""自动提取的 kyc_info_extend 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="kyc_info_extend", description="KYC信息扩展表")
class KycInfoExtend:
    COLUMNS = {
        "account_id": {"type": "uuid", "description": "账户ID"},
        "poa_doc_type": {"type": "varchar", "description": "住址证明文件类型"},
        "poa_doc_url_list": {"type": "jsonb", "description": "住址证明文件URL列表"},
        "poa_doc_date": {"type": "timestamptz", "description": "住址证明文件日期"},
        "address_line1": {"type": "varchar", "description": "地址行1"},
        "address_line2": {"type": "varchar", "description": "地址行2"},
        "state": {"type": "varchar", "description": "州"},
        "city": {"type": "varchar", "description": "城市"},
        "postal_code": {"type": "varchar", "description": "邮政编码"},
        "country": {"type": "varchar", "description": "国家"},
        "employment_status": {"type": "varchar", "description": "工作状态"},
        "employer_name": {"type": "varchar", "description": "就业公司名字"},
        "employment_job_industry": {"type": "varchar", "description": "行业"},
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
