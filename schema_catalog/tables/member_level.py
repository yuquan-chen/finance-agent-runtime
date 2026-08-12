"""自动提取的 member_level 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="member_level", description="")
class MemberLevel:
    COLUMNS = {
        "code": {"type": "varchar", "nullable": False, "description": "编码"},
        "type": {"type": "varchar", "nullable": False, "description": "会员类型"},
        "name": {"type": "varchar", "nullable": False, "description": "名称"},
        "icon": {"type": "varchar", "description": "图标"},
        "account_type": {"type": "varchar", "description": "客户类型"},
        "apple_product_id": {"type": "varchar", "nullable": False, "description": "苹果商品ID"},
        "google_product_id": {"type": "varchar", "nullable": False, "description": "谷歌商品ID"},
        "price": {"type": "numeric", "nullable": False, "description": "标准企业/个人价格"},
        "duration": {"type": "text", "nullable": False, "description": "会员时长"},
        "duration_unit": {"type": "varchar", "nullable": False, "description": "会员时长单位"},
        "offshore_price": {"type": "numeric", "description": "离岸企业价格"},
        "commission_level": {"type": "text", "description": "返佣等级"},
        "support_vcc_skin": {"type": "boolean", "description": "VCC节日卡面"},
        "support_custom_skin": {"type": "boolean", "description": "自定义卡面"},
        "card_types": {"type": "json", "description": "VCC卡类型：多选 虚拟卡/实体卡"},
        "free_kyt_count": {"type": "text", "description": "KYT反洗钱免费次数"},
        "free_card_count": {"type": "text", "description": "免费开卡数量"},
        "benefits_description": {"type": "varchar", "description": "会员权益描述"},
        "gift_level_id": {"type": "uuid", "description": "赠送会员等级id"},
        "gift_quantity": {"type": "text", "description": "赠送会员等级数量"},
        "status": {"type": "varchar", "description": "状态"},
        "operator_id": {"type": "uuid", "description": "操作人"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
