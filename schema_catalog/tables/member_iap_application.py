"""自动提取的 member_iap_application 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="member_iap_application", description="内购申请表（tracking IAP 申请） 参考 cdd_kyc 的 is_last 设计：客户可多次申请，is_last 标记最新一条 内购完成后根据此表创建 member_order 记录")
class MemberIapApplication:
    COLUMNS = {
        "account_id": {"type": "uuid", "nullable": False, "description": "客户id"},
        "level_id": {"type": "uuid", "nullable": False, "description": "等级id"},
        "platform": {"type": "varchar", "description": "平台 apple | google"},
        "status": {"type": "varchar", "description": "申请状态"},
        "is_last": {"type": "boolean", "description": "是否为最新申请"},
        "order_type": {"type": "varchar", "description": "订单类型"},
        "amount": {"type": "numeric", "nullable": False, "description": "订单金额"},
        "currency": {"type": "varchar", "nullable": False, "description": "币种"},
        "start_time": {"type": "timestamptz", "nullable": False, "description": "等级开始时间"},
        "end_time": {"type": "timestamptz", "nullable": False, "description": "等级结束时间"},
        "member_order_id": {"type": "uuid", "description": "关联的 member_order id（完成后写入）"},
        "raw_data": {"type": "jsonb", "description": "原始数据"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
