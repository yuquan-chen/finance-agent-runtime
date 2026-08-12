"""自动提取的 card_fee 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="card_fee", description="")
class CardFee:
    COLUMNS = {
        "account_id": {"type": "uuid"},
        "card_transaction_id": {"type": "uuid"},
        "action_fee": {"type": "numeric", "description": "交易处理费"},
        "fx_fee": {"type": "numeric", "description": "换汇加点fee"},
        "decline_fee": {"type": "numeric", "description": "拒付费"},
        "reversal_fee": {"type": "numeric", "description": "交易撤销费"},
        "refund_fee": {"type": "numeric", "description": "退款费(总)"},
        "auth_fee": {"type": "numeric", "description": "交易授权费"},
        "atm_fee": {"type": "numeric", "description": "ATM取现费"},
        "applepay_fee": {"type": "numeric", "description": "ApplePay手续费"},
        "append_action_fee": {"type": "numeric", "description": "机构追加的交易处理费"},
        "append_fx_fee": {"type": "numeric", "description": "机构追加的换汇加点fee"},
        "digital_wallet_fee": {"type": "numeric", "description": "数字钱包手续费"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
