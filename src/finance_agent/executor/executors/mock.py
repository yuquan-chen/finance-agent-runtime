"""Mock 执行器工厂。"""
from __future__ import annotations

from finance_agent.executor.executor_registry import register_executor
from finance_agent.executor.mock_executor import MockExecutor


@register_executor("mock")
def create_mock(settings, policy):
    return MockExecutor(policy)
