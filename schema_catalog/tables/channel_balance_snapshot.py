"""自动提取的 channel_balance_snapshot 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="channel_balance_snapshot", description="存储card，va 渠道账户余额数据")
class ChannelBalanceSnapshot:
    COLUMNS = {
        "va_entity_id": {"type": "varchar", "description": "渠道账户id"},
        "cw_tag": {"type": "varchar", "description": "数据来源tag"},
        "account_type": {"type": "varchar", "description": "账号类型（自有/客户）"},
        "type": {"type": "varchar", "description": "渠道类别（va/cw）"},
        "channel": {"type": "varchar", "description": "渠道名称"},
        "currency": {"type": "varchar", "description": "渠道余额币种或者货币"},
        "available": {"type": "numeric", "description": "余额"},
        "base_available": {"type": "numeric", "description": "基于基准货币余额"},
        "rate": {"type": "numeric", "description": "产生记录时转换至基础币种利率"},
        "sync_batch": {"type": "varchar", "description": "同步批次"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
