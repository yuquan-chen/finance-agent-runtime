"""自动提取的 va_transfer_config 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="va_transfer_config", description="")
class VaTransferConfig:
    COLUMNS = {
        "account_id": {"type": "varchar", "nullable": False, "description": "账户ID"},
        "channel": {"type": "varchar", "description": "渠道"},
        "from_user_no": {"type": "varchar", "description": "转出方用户编号"},
        "to_user_no": {"type": "varchar", "description": "转入方用户编号"},
        "reason": {"type": "varchar", "description": "失败原因"},
        "status": {"type": "varchar", "description": "交易状态"},
        "process_status": {"type": "varchar", "description": "转账配置处理状态"},
        "raw": {"type": "json", "description": "记录渠道输入输出"},
        "complete_at": {"type": "timestamptz", "description": "完成时间"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
