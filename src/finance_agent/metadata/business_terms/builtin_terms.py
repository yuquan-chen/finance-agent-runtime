"""内置业务术语（装饰器注册）。"""
from finance_agent.metadata.business_registry import register_business_term


@register_business_term(
    name="退款",
    description="退款类交易，包含部分退款和全额退款。",
    aliases=["refund", "退回", "退单"],
    candidate_fields=["type"],
    filters=[{"field": "type", "op": "=", "value": "refund"}],
)
def _():
    pass


@register_business_term(
    name="冲正",
    description="冲正交易，通常用于撤销错误交易。",
    aliases=["reversal", "撤销", "冲销"],
    candidate_fields=["type"],
    filters=[{"field": "type", "op": "=", "value": "reversal"}],
)
def _():
    pass
