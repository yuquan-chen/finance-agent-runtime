"""时间趋势操作。"""
from finance_agent.operations.handler_registry import register_operation


@register_operation(
    name="trend",
    title="时间趋势",
    description="按时间看指标怎么变化的。例：每月消费金额走势、每天交易笔数变化",
)
def _():
    pass
