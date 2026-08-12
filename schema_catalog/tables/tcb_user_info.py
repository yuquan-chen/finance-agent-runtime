"""自动提取的 tcb_user_info 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="tcb_user_info", description="")
class TcbUserInfo:
    COLUMNS = {
        "card_holder_id": {"type": "uuid", "description": "持卡人ID"},
        "account_id": {"type": "uuid", "description": "账户ID"},
        "channel_user_id": {"type": "varchar", "description": "Unique ID of user"},
        "activation_code": {"type": "varchar", "description": "Unique activation code needed to activate user"},
        "employee_number": {"type": "varchar", "description": "An employee number to associate with this account"},
        "user_type": {"type": "varchar", "description": "Type of user you are creating"},
        "first_name": {"type": "varchar", "description": "First name to be associated with user"},
        "last_name": {"type": "varchar", "description": "Last name to be associated with user"},
        "email": {"type": "varchar", "description": "Email to be associated with user"},
        "phone_number": {"type": "varchar", "description": "Phone number to be associated with user"},
        "shipping_address1": {"type": "varchar", "description": "Primary street address for shipping physical cards"},
        "shipping_address2": {"type": "varchar", "description": "Secondary street address for shipping physical cards"},
        "shipping_city": {"type": "varchar", "description": "City associated with shipping address"},
        "shipping_state": {"type": "varchar", "description": "State associated with shipping address"},
        "shipping_zip": {"type": "varchar", "description": "Zip code associated with shipping address"},
        "billing_address_type": {"type": "varchar", "description": "Specifies if billing address will be address user has saved on profile, address of account, or specified address using billing fields"},
        "billing_address1": {"type": "varchar", "description": "Primary billing address used for AVS (Address Verification System) on digital cards"},
        "billing_address2": {"type": "varchar", "description": "Secondary billing address used for AVS (Address Verification System) on digital cards"},
        "billing_city": {"type": "varchar", "description": "Billing City associated with the billing address used for AVS on digital cards"},
        "billing_state": {"type": "varchar", "description": "Billing state associated with the billing address used for AVS on digital cards"},
        "billing_zip": {"type": "varchar", "description": "Billing zip code associated with the billing address used for AVS on digital cards"},
        "status": {"type": "varchar", "description": "状态"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
