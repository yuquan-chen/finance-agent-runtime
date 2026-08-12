"""自动提取的 fireblocks_asset 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="fireblocks_asset", description="")
class FireblocksAsset:
    COLUMNS = {
        "asset_id": {"type": "varchar", "description": "fireblocks发起交易时需要的"},
        "asset_name": {"type": "varchar", "description": "asset名称"},
        "currency": {"type": "varchar", "description": "币种"},
        "chain": {"type": "varchar", "description": "链"},
        "decimals": {"type": "text", "description": "精度"},
        "contract_address": {"type": "varchar", "description": "合约地址"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
