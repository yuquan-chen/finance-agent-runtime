"""执行器 Executor 注册表。

使用 @register_executor 装饰器注册执行器工厂函数。
新增执行器只需新建文件 + 加装饰器，不需要修改 runtime.py。
"""
from __future__ import annotations

import importlib
import pkgutil
from functools import lru_cache
from typing import Any, Callable


# ---------------------------------------------------------------------------
# 全局待注册列表
# ---------------------------------------------------------------------------

_pending_executors: dict[str, Callable] = {}


def register_executor(mode: str) -> Callable:
    """装饰器：注册一个执行器工厂函数。

    用法：
        @register_executor("mock")
        def create_mock(settings, policy):
            return MockExecutor(policy)

    工厂函数签名：(settings, policy) → executor instance
    """
    def decorator(fn: Callable) -> Callable:
        _pending_executors[mode] = fn
        return fn
    return decorator


# ---------------------------------------------------------------------------
# 执行器注册表
# ---------------------------------------------------------------------------

class ExecutorRegistry:
    """执行器注册表。"""

    def __init__(self) -> None:
        self._factories: dict[str, Callable] = {}

    def register(self, mode: str, factory: Callable) -> None:
        self._factories[mode] = factory

    def get(self, mode: str) -> Callable | None:
        return self._factories.get(mode)

    def supported_modes(self) -> list[str]:
        return list(self._factories.keys())

    def create(self, mode: str, settings: Any, policy: Any) -> Any:
        """查找并创建对应执行器。"""
        factory = self.get(mode)
        if not factory:
            raise ValueError(f"unsupported executor mode: {mode}")
        executor = factory(settings, policy)
        if not callable(getattr(executor, "execute_method", None)):
            raise TypeError(
                f"executor mode {mode!r} must implement execute_method(method, extra_tables=...)"
            )
        return executor


# ---------------------------------------------------------------------------
# 自动发现 + 构建默认注册表
# ---------------------------------------------------------------------------

def _discover_executors() -> None:
    """扫描 finance_agent.executor.executors 包，触发所有 @register_executor 装饰器。"""
    try:
        package = importlib.import_module("finance_agent.executor.executors")
    except ModuleNotFoundError:
        return
    for _importer, modname, _ispkg in pkgutil.iter_modules(package.__path__):
        importlib.import_module(f"finance_agent.executor.executors.{modname}")


@lru_cache(maxsize=1)
def get_default_executor_registry() -> ExecutorRegistry:
    """返回预注册所有内置执行器的注册表。"""
    _discover_executors()

    registry = ExecutorRegistry()
    for mode, factory in _pending_executors.items():
        registry.register(mode, factory)
    return registry
