"""自动提取的 pay_deposit 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="pay_deposit", description="")
class PayDeposit:
    COLUMNS = {
        "id_no": {"type": "bigint"},
        "account_id": {"type": "uuid", "description": "账户ID"},
        "amount": {"type": "numeric", "description": "订单金额（支付或退款）"},
        "fee": {"type": "numeric", "description": "交易手续费"},
        "currency": {"type": "varchar", "description": "订单创建选定币种"},
        "status": {"type": "varchar", "description": "订单标准状态"},
        "sub_status": {"type": "varchar", "description": "子状态"},
        "balance_id": {"type": "uuid", "description": "关联的余额ID"},
        "pay_type": {"type": "varchar", "description": "支付方式"},
        "pay_method_info": {"type": "jsonb", "description": "支付信息"},
        "source_id": {"type": "varchar", "description": "来源ID"},
        "payer": {"type": "varchar", "description": "支付者 币安用户openid"},
        "raw_data": {"type": "jsonb", "description": "原始数据"},
        "transaction_at": {"type": "timestamptz", "description": "订单创建时间"},
        "completed_at": {"type": "timestamptz", "description": "订单完成时间"},
        "batch_id": {"type": "varchar"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
