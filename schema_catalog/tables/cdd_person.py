"""自动提取的 cdd_person 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="cdd_person", description="CustomerDueDiligence person-info")
class CddPerson:
    COLUMNS = {
        "account_id": {"type": "uuid"},
        "kyc_id": {"type": "uuid"},
        "name": {"type": "jsonb", "nullable": False, "description": "名字"},
        "country": {"type": "varchar", "description": "国籍/所在地"},
        "birthday": {"type": "varchar", "description": "生日,格式：YYYY-MM-DD"},
        "address": {"type": "json", "description": "证件地址"},
        "attachment": {"type": "json", "description": "个人附件"},
        "start_date": {"type": "varchar", "description": "证件起始日期,格式：YYYY-MM-DD"},
        "expiration_date": {"type": "varchar", "description": "证件过期日期,格式：YYYY-MM-DD"},
        "number": {"type": "varchar", "nullable": False, "description": "证件号"},
        "type": {"type": "varchar", "nullable": False, "description": "证件类型"},
        "from_id": {"type": "uuid", "nullable": False, "description": "溯源id"},
        "share_percent": {"type": "text", "description": "占股比例"},
        "is_representative": {"type": "boolean", "description": "是否是法人"},
        "is_beneficiary": {"type": "boolean", "description": "是否为受益人"},
        "is_authorized": {"type": "boolean", "description": "是否是被授权人"},
        "is_contact": {"type": "boolean", "description": "是否是联络人"},
        "verify_type": {"type": "varchar", "description": "验证方式"},
        "industry": {"type": "varchar", "description": "行业信息"},
        "position": {"type": "varchar", "description": "职位信息"},
        "salary": {"type": "numeric", "description": "薪资"},
        "tax_residency": {"type": "varchar", "description": "税务居民类型"},
        "tax_countries": {"type": "jsonb", "description": "税务居民国家"},
        "contact_info": {"type": "jsonb", "description": "联络人信息"},
        "product_binding_info": {"type": "jsonb", "description": "产品绑定信息"},
        "account_manager": {"type": "varchar", "description": "账户经理"},
        "aml_info": {"type": "jsonb", "description": "cdd&& aml 信息"},
        "aml_review_required_count": {"type": "text", "description": "要求aml复核次数"},
        "gender": {"type": "varchar", "description": "性别"},
        "purpose": {"type": "varchar", "description": "使用目的"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
