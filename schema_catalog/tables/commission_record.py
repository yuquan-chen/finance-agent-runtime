"""自动提取的 commission_record 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="commission_record", description="")
class CommissionRecord:
    COLUMNS = {
        "account_id": {"type": "uuid", "description": "被邀请者id"},
        "level": {"type": "text", "nullable": False, "description": "被邀请者佣金等级"},
        "type": {"type": "varchar", "nullable": False, "description": "交易类型"},
        "trx_id": {"type": "uuid", "description": "交易id"},
        "trx_at": {"type": "timestamptz", "description": "交易时间"},
        "order_num": {"type": "text", "description": "订单号"},
        "order_amount": {"type": "numeric", "description": "交易总金额（基于usd）"},
        "order_fee": {"type": "numeric", "description": "交易手续费(基于usd)"},
        "invitee_level": {"type": "text", "nullable": False, "description": "邀请者返佣等级"},
        "rate": {"type": "numeric", "description": "返佣比例"},
        "invitee_account_id": {"type": "uuid", "description": "佣金获得者账号id"},
        "commission_amount": {"type": "numeric", "description": "返佣金额(基于usd)"},
        "status": {"type": "varchar", "description": "返佣状态"},
        "message_id": {"type": "uuid", "description": " 关联mq请求消息id"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
