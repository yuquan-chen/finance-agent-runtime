"""分布统计操作。"""
from finance_agent.operations.handler_registry import register_operation


@register_operation(
    name="distribution",
    title="分布统计",
    description="统计某个分类各有多少条。例：各交易状态有多少笔、各渠道的交易笔数",
)
def _():
    pass
