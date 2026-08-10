"""通用操作注册表（声明型）。

每个操作只存元数据：name、title、description。
LLM 看到操作列表后自己写 SQL，系统只管校验和执行。

使用 @register_operation 装饰器自动注册，不需要手动改 get_default_registry()。
"""
from __future__ import annotations

import importlib
import pkgutil
from functools import lru_cache
from typing import Any, Callable

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# 操作模型（纯元数据）
# ---------------------------------------------------------------------------

class OperationHandler(BaseModel):
    """一个通用操作的定义（纯元数据）。"""
    name: str
    title: str
    description: str


# ---------------------------------------------------------------------------
# 全局待注册列表（装饰器往里放，get_default_registry() 读出来）
# ---------------------------------------------------------------------------

_pending_operations: list[dict[str, str]] = []


def register_operation(
    *,
    name: str,
    title: str,
    description: str,
) -> Callable:
    """装饰器：注册一个通用操作。

    用法：
        @register_operation(
            name="top_n",
            title="Top N 排名",
            description="找某个指标最高的前 N 名。例：消费最多的 10 个客户",
        )
        def _placeholder():
            pass
    """
    def decorator(fn: Callable) -> Callable:
        _pending_operations.append({
            "name": name,
            "title": title,
            "description": description,
        })
        return fn
    return decorator


# ---------------------------------------------------------------------------
# 注册表
# ---------------------------------------------------------------------------

class OperationHandlerRegistry:
    """通用操作注册表（纯元数据）。"""

    def __init__(self) -> None:
        self._handlers: dict[str, OperationHandler] = {}

    def register(self, handler: OperationHandler) -> None:
        self._handlers[handler.name] = handler

    # ---- 查询 ----

    def get(self, name: str) -> OperationHandler | None:
        return self._handlers.get(name)

    def names(self) -> list[str]:
        return list(self._handlers.keys())

    def manifest_for_llm(self) -> list[dict[str, str]]:
        """给 LLM 看的精简索引：name + title + description。"""
        return [
            {"name": h.name, "title": h.title, "description": h.description}
            for h in self._handlers.values()
        ]


# ---------------------------------------------------------------------------
# 自动发现 + 构建默认注册表
# ---------------------------------------------------------------------------

def _discover_handlers() -> None:
    """扫描 finance_agent.operations.handlers 包，触发所有 @register_operation 装饰器。"""
    try:
        package = importlib.import_module("finance_agent.operations.handlers")
    except ModuleNotFoundError:
        return
    for _importer, modname, _ispkg in pkgutil.iter_modules(package.__path__):
        importlib.import_module(f"finance_agent.operations.handlers.{modname}")


@lru_cache(maxsize=1)
def get_default_registry() -> OperationHandlerRegistry:
    """返回预注册所有内置操作的注册表。

    自动扫描 finance_agent.operations.handlers 包下所有模块，
    收集 @register_operation 装饰器注册的操作。
    """
    _discover_handlers()

    registry = OperationHandlerRegistry()

    for op in _pending_operations:
        registry.register(OperationHandler(
            name=op["name"],
            title=op["title"],
            description=op["description"],
        ))

    return registry
