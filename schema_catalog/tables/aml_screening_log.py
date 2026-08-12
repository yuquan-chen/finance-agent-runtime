"""自动提取的 aml_screening_log 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="aml_screening_log", description="")
class AmlScreeningLog:
    COLUMNS = {
        "screening_business": {"type": "varchar", "description": "筛查业务"},
        "aml_channel": {"type": "varchar", "description": "AML渠道：sumsub/didit"},
        "business_id": {"type": "varchar", "description": "业务ID（如 payee.id）"},
        "screening_time": {"type": "timestamptz", "description": "筛查时间"},
        "level_name": {"type": "varchar", "description": "Sumsub levelName / didit level"},
        "external_user_id": {"type": "varchar", "description": "Sumsub externalUserId / didit external id"},
        "applicant_id": {"type": "varchar", "description": "Sumsub applicantId"},
        "result": {"type": "varchar", "description": "结果：pending/GREEN/RED/failed"},
        "review_status": {"type": "varchar", "description": "Sumsub reviewStatus"},
        "payload": {"type": "jsonb", "description": "结果详情/原始payload"},
        "meta": {"type": "jsonb", "description": "扩展字段（如 ongoingMonitoring.enabled）"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
