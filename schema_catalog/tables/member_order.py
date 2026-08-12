"""自动提取的 member_order 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="member_order", description="")
class MemberOrder:
    COLUMNS = {
        "id_no": {"type": "bigint", "nullable": False, "description": "订单号"},
        "order_type": {"type": "varchar", "description": "订单类型"},
        "account_id": {"type": "uuid", "nullable": False, "description": "客户id"},
        "level_id": {"type": "uuid", "nullable": False, "description": "等级id"},
        "origin_amount": {"type": "numeric", "nullable": False, "description": "原始金额，产品价"},
        "amount": {"type": "numeric", "nullable": False, "description": "订单金额"},
        "discount_amount": {"type": "numeric", "nullable": False, "description": "优惠金额"},
        "fee": {"type": "numeric", "nullable": False, "description": "手续费"},
        "pay_amount": {"type": "numeric", "nullable": False, "description": "实际付款金额"},
        "currency": {"type": "varchar", "nullable": False, "description": "币种"},
        "balance_id": {"type": "uuid", "description": "账户id。应用内购(Apple/Google)走渠道支付，不涉及客户余额，为 null"},
        "status": {"type": "varchar", "description": "状态"},
        "use_status": {"type": "varchar", "description": "使用状态"},
        "completed_at": {"type": "timestamptz", "nullable": False, "description": "完成时间"},
        "trace_id": {"type": "uuid", "description": "关联交易表"},
        "source_id": {"type": "varchar", "description": "三方交易表ID"},
        "original_transaction_id": {"type": "varchar", "description": "原始交易表ID"},
        "start_time": {"type": "timestamptz", "nullable": False, "description": "开始时间"},
        "end_time": {"type": "timestamptz", "nullable": False, "description": "结束时间"},
        "actual_end_time": {"type": "timestamptz", "nullable": False, "description": "实际到期时间"},
        "pre_level_id": {"type": "uuid", "description": "上一个会员等级id"},
        "pre_start_time": {"type": "timestamptz", "nullable": False, "description": "上一个会员开始时间"},
        "pre_end_time": {"type": "timestamptz", "nullable": False, "description": "上一个会员结束时间"},
        "subscription_id": {"type": "uuid", "description": "订阅表id"},
        "platform": {"type": "varchar", "description": "平台"},
        "exchange_code": {"type": "varchar", "description": "兑换码"},
        "exchange_code_owner": {"type": "uuid", "description": "兑换码所属账户id"},
        "raw_data": {"type": "jsonb", "description": "原始数据"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
