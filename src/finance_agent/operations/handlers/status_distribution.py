"""状态分布操作。"""
from finance_agent.operations.handler_registry import register_operation


@register_operation(
    name="status_distribution",
    title="状态分布",
    description="统计交易状态各有多少笔。例：completed 有多少、failed 有多少、pending 有多少",
)
def _():
    pass
