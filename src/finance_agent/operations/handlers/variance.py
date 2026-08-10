"""波动分析操作。"""
from finance_agent.operations.handler_registry import register_operation


@register_operation(
    name="variance",
    title="波动分析",
    description="看数值波动大不大。例：消费金额的波动情况、各客户消费金额的差异程度",
)
def _():
    pass
