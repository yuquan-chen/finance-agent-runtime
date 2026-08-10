"""Top N 排名操作。"""
from finance_agent.operations.handler_registry import register_operation


@register_operation(
    name="top_n",
    title="Top N 排名",
    description="找某个指标最高的前 N 名。例：消费最多的 10 个客户、金额最大的 5 笔交易",
)
def _():
    pass
