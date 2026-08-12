"""自动提取的 account_fee 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="account_fee", description="* 费率优先级 账户费率 > 邀请码费率 > 系统默认费率")
class AccountFee:
    COLUMNS = {
        "account_id": {"type": "uuid", "description": "账户id"},
        "status": {"type": "varchar", "description": "状态"},
        "type": {"type": "varchar", "description": "配置类型"},
        "number": {"type": "numeric", "description": "值"},
        "condition": {"type": "varchar", "description": "辅助的条件"},
        "math_type": {"type": "varchar", "description": "计算方式"},
        "effective_start": {"type": "timestamptz", "description": "生效开始时间"},
        "effective_end": {"type": "timestamptz", "description": "生效结束时间"},
        "use_to": {"type": "varchar", "description": "用途"},
        "raw": {"type": "json", "description": "结构数据"},
        "big_type": {"type": "varchar", "description": "大类型"},
        "l_basic_number": {"type": "numeric", "description": "企业Basic会员值"},
        "l_premium_number": {"type": "numeric", "description": "企业Premium会员值"},
        "l_platinum_number": {"type": "numeric", "description": "企业Platinum会员值"},
        "l_ultra_number": {"type": "numeric", "description": "企业Ultra会员值"},
        "p_basic_number": {"type": "numeric", "description": "个人Basic会员值"},
        "p_premium_number": {"type": "numeric", "description": "个人Premium会员值"},
        "p_platinum_number": {"type": "numeric", "description": "个人Platinum会员值"},
        "p_ultra_number": {"type": "numeric", "description": "个人Ultra会员值"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
