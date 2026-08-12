"""自动提取的 user_extend 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="user_extend", description="")
class UserExtend:
    COLUMNS = {
        "user_id": {"type": "uuid"},
        "google_otp_auth_key": {"type": "varchar", "description": "GA key"},
        "enable_google_otp_auth": {"type": "boolean", "description": "GA 是否启用"},
        "last_login_time": {"type": "timestamptz", "description": "最后登录时间"},
        "last_login_device": {"type": "varchar", "description": "最后登录设备"},
        "last_app_version": {"type": "varchar", "description": "最后使用的app版本号"},
        "register_device": {"type": "varchar", "description": "注册设备"},
        "history_passwords": {"type": "json", "description": "历史密码"},
        "update_password_time": {"type": "timestamptz", "description": "最后修改密码时间"},
        "fcm_token": {"type": "varchar", "description": "firebase_registration_token"},
        "fcm_token_md5": {"type": "varchar", "description": "fcm_token 的 md5，用于查重与解绑"},
        "lang": {"type": "varchar", "description": "使用的语言"},
        "origin_type": {"type": "varchar", "description": "来源"},
        "wallet_address": {"type": "text", "description": "钱包地址"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
