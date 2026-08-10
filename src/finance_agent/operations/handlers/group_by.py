"""分组分析操作。"""
from finance_agent.operations.handler_registry import register_operation


@register_operation(
    name="group_by",
    title="分组分析",
    description="按某个维度分组算汇总。例：各渠道的消费总额、各客户的交易笔数",
)
def _():
    pass
