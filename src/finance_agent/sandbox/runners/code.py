"""Code Runner — 在受限 Python 环境中执行代码方法。"""
from __future__ import annotations

from typing import Any

from finance_agent.sandbox.provider import SandboxExecutionRequest
from finance_agent.sandbox.runner_registry import register_runner


class SandboxCodeError(RuntimeError):
    pass


SAFE_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "range": range,
    "round": round,
    "sorted": sorted,
    "str": str,
    "sum": sum,
}


@register_runner("code")
def run_code(request: SandboxExecutionRequest) -> Any:
    """执行代码方法。"""
    method = request.method
    if not method.code:
        raise SandboxCodeError("code method has no code")
    namespace: dict[str, Any] = {"__builtins__": SAFE_BUILTINS}
    exec(method.code, namespace)  # noqa: S102 - execution is intentionally confined to SAFE_BUILTINS
    functions = [value for key, value in namespace.items() if callable(value) and not key.startswith("__")]
    if len(functions) != 1:
        raise SandboxCodeError("code method must define exactly one callable")
    required_field = _field_name(method.required_fields[0], "total_amount") if method.required_fields else "total_amount"
    return functions[0](request.rows, required_field)


def _field_name(qualified: str, fallback: str) -> str:
    if "." in qualified:
        return qualified.split(".", 1)[1]
    return qualified or fallback
