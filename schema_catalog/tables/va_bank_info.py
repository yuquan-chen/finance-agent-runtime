"""自动提取的 va_bank_info 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="va_bank_info", description="")
class VaBankInfo:
    COLUMNS = {
        "account_id": {"type": "uuid", "description": "我方账户ID"},
        "channel_name": {"type": "varchar", "description": "渠道名称"},
        "account_name": {"type": "text", "description": "银行账户名称"},
        "account_holder_address": {"type": "json", "description": "持有人地址"},
        "bank_name": {"type": "text", "description": "银行名称"},
        "bank_account_no": {"type": "text", "description": "银行账户号"},
        "bankCode": {"type": "text", "description": "银行号"},
        "branchCode": {"type": "text", "description": "支行号"},
        "bank_account_type": {"type": "text", "description": "银行账户类型"},
        "bank_address": {"type": "json", "description": "银行账户地址"},
        "bic_swift": {"type": "text", "description": "SWIFT/BIC代码"},
        "routing_type": {"type": "text", "description": "银行路线类型"},
        "routing_number": {"type": "text", "description": "银行路线号码"},
        "raw_data": {"type": "json", "description": "原始数据"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
