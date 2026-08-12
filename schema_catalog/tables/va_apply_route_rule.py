"""自动提取的 va_apply_route_rule 表 schema。"""
from finance_agent.metadata.table_registry import register_table


@register_table(name="va_apply_route_rule", description="单语言下对客/运营展示的文案块；键可随业务扩展（如 priority_note、compliance_hint）。 读取时按请求语言取 locale，缺省可回落 zh_CN / en_US。 / export interface VaApplyRouteRuleDisplayLocaleBlock { collection_methods?: string; opening_time_estimate?: string; pricing_note?: string; fx_markup_note?: string; kyc_difficulty?: string; /** 路线标签（对客 tags[]，不进入 display） */ tag_1?: string; tag_2?: string; tag_3?: string; tag_4?: string; [key: string]: string | undefined; } export const VA_APPLY_ROUTE_TAG_KEYS = ['tag_1', 'tag_2', 'tag_3', 'tag_4'] as const; export interface VaApplyRouteKeyParts { va_channel_name: string; country_code: string; va_currency: string; bank_name_enum: string; payee_type: string; } /** 生成稳定 route_key（全小写、下划线连接），用于 AccountFee.condition 等。 例：va_008_sg_sgd_va008_ocbc_local_single / export function buildVaApplyRouteKey(parts: VaApplyRouteKeyParts): string { return [parts.va_channel_name, parts.country_code, parts.va_currency, parts.bank_name_enum, parts.payee_type] .map((s) => String(s).trim().toLowerCase()) .join('_'); } /** locale（如 zh_CN、en_US）→ 展示文案块 */ export type VaApplyRouteRuleDisplay = Record<string, VaApplyRouteRuleDisplayLocaleBlock>; /** VA 申请账户路由（收款渠道 / 合作行维度） 由运营在库中维护，用于 calculateChannelNameAndPayeeCurrencies 解析 channel 与 payee_currencies。")
class VaApplyRouteRule:
    COLUMNS = {
        "enabled": {"type": "boolean", "description": "是否启用"},
        "sort_order": {"type": "text", "description": "排序，大者优先（同键多条时）"},
        "region_label": {"type": "varchar", "description": "地区说明（列表筛选用，可与 rule_display 并存）"},
        "partner_bank": {"type": "varchar", "description": "合作银行简称（列表筛选用）"},
        "country_code": {"type": "varchar", "description": "国家/地区代码，对应 VaAllCountryCodeEnum"},
        "bank_name": {"type": "varchar", "description": "开户行展示名，与 bank_name_enum 分离"},
        "bank_name_enum": {"type": "varchar", "description": "开户行枚举值 VaAllBankNameEnum"},
        "payee_type": {"type": "varchar", "description": "收款账户类型 VaAllPayeeTypeEnum"},
        "va_currency": {"type": "varchar"},
        "va_channel_name": {"type": "varchar", "description": "VAChannelNameEnum"},
        "payee_currencies": {"type": "jsonb", "description": "该 VA 支持的 payee_currencies 列表"},
        "route_key": {"type": "varchar", "description": "稳定路由键（建议下划线语义化）"},
        "rule_display": {"type": "jsonb", "description": "多语言规则展示 JSON"},
        "id": {"type": "uuid", "nullable": False, "description": "主键"},
        "remarks": {"type": "text"},
        "created_at": {"type": "timestamptz"},
        "update_at": {"type": "timestamptz"},
        "delete_at": {"type": "timestamptz"},
        "version": {"type": "integer", "nullable": False},
    }
