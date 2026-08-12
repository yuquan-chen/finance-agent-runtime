"""自动提取的 card_channel 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="card_channel", description="")
class CardChannel:
    COLUMNS = {
        "bin": {"type": "text", "description": "银行识别码"},
        "organization": {"type": "varchar", "description": "卡组织"},
        "issuer_country": {"type": "text", "description": "发卡行国家"},
        "channel_name": {"type": "varchar", "description": "渠道方名称"},
        "type": {"type": "varchar", "description": "卡类型"},
        "limit": {"type": "text", "description": "最大限额"},
        "currency": {"type": "varchar", "description": "币种"},
        "global_limit_window": {"type": "text", "description": "限额方式"},
        "card_class": {"type": "text", "description": "卡类别"},
        "support_avs": {"type": "text", "description": "是否支持AVS"},
        "support_3ds": {"type": "text", "description": "是否支持3DS"},
        "support_google_pay": {"type": "text", "description": "是否支持google pay"},
        "support_apple_pay": {"type": "text", "description": "是否支持apple pay"},
        "support_wechat_pay": {"type": "text", "description": "是否支持wechat pay"},
        "support_alipay": {"type": "text", "description": "是否支持alipay"},
        "support_others": {"type": "json", "description": "是否支持alipay"},
        "status": {"type": "varchar", "description": "是否可用"},
        "order": {"type": "bigint", "description": "排序,越大排序越前"},
        "source_id": {"type": "varchar", "description": "三方id"},
        "raw": {"type": "json", "description": "三方原始数据"},
        "require_register": {"type": "text", "nullable": False, "description": "是否需要注册持卡人"},
        "support_physical": {"type": "text", "nullable": False, "description": "是否支持实体卡"},
        "support_function_types": {"type": "json", "description": "支持的卡功能类型"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
