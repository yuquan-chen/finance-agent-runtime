"""自动提取的 payout_payee 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="payout_payee", description="")
class PayoutPayee:
    COLUMNS = {
        "account_id": {"type": "uuid", "nullable": False, "description": "账户ID"},
        "currency": {"type": "varchar", "description": "币种"},
        "country": {"type": "varchar", "description": "开户银行所在地"},
        "receive_type": {"type": "varchar", "description": "付款方式"},
        "payee_type": {"type": "varchar", "description": "收款类型 Company/Individual"},
        "first_name": {"type": "varchar", "description": "名"},
        "last_name": {"type": "varchar", "description": "姓"},
        "user_name": {"type": "varchar", "description": "个人完整姓名或者公司名称"},
        "bank_name": {"type": "varchar", "description": "银行名称"},
        "bic_swift": {"type": "varchar", "description": "BIC代码或Swift Code"},
        "account_number": {"type": "varchar", "description": "银行账号 | iban"},
        "bank_code": {"type": "varchar", "description": "银行代码"},
        "payee_address": {"type": "json", "description": "受益人地址"},
        "label": {"type": "varchar", "description": "标签/备注"},
        "last_used_at": {"type": "timestamptz", "description": "最近使用时间"},
        "sub_receive_type": {"type": "varchar", "description": "子付款方式"},
        "routing_type1": {"type": "varchar", "description": "路由线路类型1"},
        "routing_number1": {"type": "varchar", "description": "路由线路号码1"},
        "routing_type2": {"type": "varchar", "description": "路由线路类型2"},
        "routing_number2": {"type": "varchar", "description": "路由线路号码2"},
        "bank_address": {"type": "json", "description": "银行地址"},
        "status": {"type": "varchar", "description": "状态"},
        "owner_type": {"type": "varchar", "description": "收款方与客户本人关系（self/other）"},
        "sort_code": {"type": "varchar", "description": "SortCode，英国本地需传"},
        "channel_payee_id": {"type": "varchar", "description": "渠道存储收款方返回的记录编号(用户主体)"},
        "extensions": {"type": "json", "description": "收款人补采字段，键 field_key 如 receiver_mobile"},
        "channel_field_values": {"type": "json", "description": "收款人渠道码表值，按渠道分桶"},
        "intermediary_bank_name": {"type": "varchar", "description": "中转银行名称"},
        "intermediary_bank_swift_code": {"type": "varchar", "description": "中转银行 Swift Code"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
