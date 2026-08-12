"""自动提取的 fireblocks_vault 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="fireblocks_vault", description="")
class FireblocksVault:
    COLUMNS = {
        "vault_account_id": {"type": "varchar", "description": "fireblocks vault account id"},
        "account_id": {"type": "uuid", "description": "主系统账户id"},
        "wallet_id": {"type": "uuid", "description": "钱包Id"},
        "customer_ref_id": {"type": "varchar", "description": "关联id"},
        "name": {"type": "varchar", "description": "名称"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
