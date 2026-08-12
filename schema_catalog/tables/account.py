"""自动提取的 account 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="account", description="")
class Account:
    COLUMNS = {
        "type": {"type": "varchar"},
        "kyc_status": {"type": "varchar", "description": "客户的KYC状态"},
        "aml_status": {"type": "varchar", "description": "aml状态"},
        "card_kyb_status": {"type": "varchar", "description": "客户的KYb状态"},
        "cw_kyb_status": {"type": "varchar", "description": "cw的KYb状态"},
        "va_kyb_status": {"type": "varchar", "description": "va的KYb状态"},
        "acquiring_kyb_status": {"type": "varchar", "description": "web3收单的KYb状态"},
        "status": {"type": "varchar"},
        "identifier_id": {"type": "varchar", "description": "账户标识符"},
        "legal_name": {"type": "text", "description": "企业/法人名称"},
        "legal_name_en": {"type": "text", "description": "企业/法人名称"},
        "last_login_time": {"type": "timestamptz", "description": "最后登录时间"},
        "white_label_id": {"type": "varchar", "description": "白标商户id"},
        "risk_level": {"type": "varchar", "description": "合规风控_风险等级"},
        "risk_score": {"type": "numeric", "description": "合规风控_风险评分"},
        "risk_data": {"type": "json", "description": "合规风控_风险要素评审结果"},
        "is_str": {"type": "boolean", "description": "合规风控_该客户是否需要提交可疑交易报告"},
        "is_monitored": {"type": "boolean", "description": "合规风控_该客户是否需要被持续监控"},
        "call_id": {"type": "varchar", "description": "API调用方ID"},
        "source": {"type": "varchar", "description": "客户来源"},
        "can_apply_va": {"type": "boolean", "description": "该客户是否可以申请va"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
