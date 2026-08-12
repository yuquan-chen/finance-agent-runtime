"""自动提取的 budget 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="budget", description="")
class Budget:
    COLUMNS = {
        "account_id": {"type": "uuid", "description": "账户id"},
        "source_id": {"type": "varchar", "description": "渠道的ID，如penny的walletId"},
        "balance_id": {"type": "uuid", "description": "钱包id"},
        "name": {"type": "varchar", "description": "名称"},
        "status": {"type": "varchar", "description": "状态"},
        "total_limit": {"type": "numeric", "description": "总设定额度"},
        "call_id": {"type": "varchar", "description": "API客户的请求ID"},
        "raw": {"type": "json", "description": "三方返回的原始数据"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
