"""沙箱 Runner 注册表。

使用 @register_runner 装饰器注册 SQL/Code 等 runner。
新增 runner 只需新建文件 + 加装饰器，不需要修改 local_provider.py。
"""
from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable
from functools import lru_cache
from typing import Any

from finance_agent.sandbox.provider import SandboxExecutionRequest

# ---------------------------------------------------------------------------
# 全局待注册列表
# ---------------------------------------------------------------------------

_pending_runners: dict[str, Callable] = {}


def register_runner(method_type: str) -> Callable:
    """装饰器：注册一个沙箱 runner。

    用法：
        @register_runner("sql")
        def run_sql(request: SandboxExecutionRequest) -> list[dict]:
            ...

    Runner 签名：接收 SandboxExecutionRequest，返回结果（list/dict/Any）。
    """
    def decorator(fn: Callable) -> Callable:
        _pending_runners[method_type] = fn
        return fn
    return decorator


# ---------------------------------------------------------------------------
# Runner 注册表
# ---------------------------------------------------------------------------

class RunnerRegistry:
    """沙箱 Runner 注册表。"""

    def __init__(self) -> None:
        self._runners: dict[str, Callable] = {}

    def register(self, method_type: str, fn: Callable) -> None:
        self._runners[method_type] = fn

    def get(self, method_type: str) -> Callable | None:
        return self._runners.get(method_type)

    def supported_types(self) -> list[str]:
        return list(self._runners.keys())

    def execute(self, request: SandboxExecutionRequest) -> Any:
        """查找并执行对应 runner。"""
        runner = self.get(request.method.method_type)
        if not runner:
            raise ValueError(f"unsupported method type: {request.method.method_type}")
        return runner(request)


# ---------------------------------------------------------------------------
# 自动发现 + 构建默认注册表
# ---------------------------------------------------------------------------

def _discover_runners() -> None:
    """扫描 finance_agent.sandbox.runners 包，触发所有 @register_runner 装饰器。"""
    try:
        package = importlib.import_module("finance_agent.sandbox.runners")
    except ModuleNotFoundError:
        return
    for _importer, modname, _ispkg in pkgutil.iter_modules(package.__path__):
        importlib.import_module(f"finance_agent.sandbox.runners.{modname}")


@lru_cache(maxsize=1)
def get_default_runner_registry() -> RunnerRegistry:
    """返回预注册所有内置 runner 的注册表。"""
    _discover_runners()

    registry = RunnerRegistry()
    for method_type, fn in _pending_runners.items():
        registry.register(method_type, fn)
    return registry
