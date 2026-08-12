"""自动提取的 account_questionnaire 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="account_questionnaire", description="* 分配给客户的问卷")
class AccountQuestionnaire:
    COLUMNS = {
        "account_id": {"type": "uuid", "nullable": False, "description": "账户ID"},
        "record_id": {"type": "uuid", "description": "记录id"},
        "input": {"type": "text", "description": "客户填写的回答"},
        "attachments": {"type": "json", "description": "客户上传附件"},
        "select_options": {"type": "json", "description": "客户选择的选项"},
        "source_id": {"type": "text", "description": "渠道问题id"},
        "source_type": {"type": "varchar", "description": "渠道类型"},
        "question": {"type": "json", "description": "题目"},
        "options": {"type": "json", "description": "选项"},
        "is_multiple": {"type": "boolean", "description": "是否多选"},
        "type": {"type": "varchar", "description": "问题类型"},
        "enabled": {"type": "boolean", "description": "是否启用"},
        "order": {"type": "integer", "description": "排序"},
        "annex_configure": {"type": "json", "description": "文件配置"},
        "parent_source_id": {"type": "varchar", "description": "父级问题id"},
        "parent_source_option": {"type": "json", "description": "父级问题选项(父级别)"},
        "map_options": {"type": "varchar", "description": "映射的选项"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
