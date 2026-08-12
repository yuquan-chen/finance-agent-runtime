"""自动提取的 table_form 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="table_form", description="")
class TableForm:
    COLUMNS = {
        "user_id": {"type": "uuid", "description": "创建人ID"},
        "name": {"type": "varchar", "description": "表单名称"},
        "business": {"type": "varchar", "description": "业务标识"},
        "description": {"type": "varchar", "description": "描述"},
        "language": {"type": "varchar", "description": "语言"},
        "status": {"type": "varchar", "description": "状态"},
        "fields": {"type": "json", "description": "表单字段配置"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
