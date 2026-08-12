"""自动提取的 chain_explorer_config 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="chain_explorer_config", description="")
class ChainExplorerConfig:
    COLUMNS = {
        "chain": {"type": "varchar", "nullable": False, "description": "链类型"},
        "type": {"type": "varchar", "nullable": False, "description": "类型"},
        "url_template": {"type": "text", "nullable": False, "description": "浏览器地址模版"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
