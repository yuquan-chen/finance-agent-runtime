"""本地沙箱 Provider。

通过 RunnerRegistry 分发到对应 runner，不硬编码 method_type。
"""
from __future__ import annotations

import time

from finance_agent.harness.analysis_schema import MockDryRunResult
from finance_agent.sandbox.provider import SandboxExecutionRequest
from finance_agent.sandbox.runner_registry import RunnerRegistry, get_default_runner_registry


class LocalProcessSandboxProvider:
    """Development sandbox provider.

    This provider is not the production security boundary. It keeps the same
    provider contract as Firecracker so the workflow can be developed locally
    on macOS while execution is still routed through one sandbox abstraction.
    """

    name = "local_process"

    def __init__(self, runner_registry: RunnerRegistry | None = None) -> None:
        self.runner_registry = runner_registry or get_default_runner_registry()

    def execute(self, request: SandboxExecutionRequest) -> MockDryRunResult:
        started = time.time()
        method = request.method
        try:
            output = self.runner_registry.execute(request)
            elapsed_ms = int((time.time() - started) * 1000)
            return MockDryRunResult(
                status="passed",
                output=output,
                input_summary={
                    "fixture": request.dataset_name,
                    "row_count": len(request.rows),
                    "elapsed_ms": elapsed_ms,
                    "runner": method.method_type,
                    "sandbox_provider": self.name,
                    "network_disabled": request.network_disabled,
                    "real_database_used": False,
                },
            )
        except Exception as exc:  # noqa: BLE001 - provider returns a structured sandbox failure
            return MockDryRunResult(
                status="failed",
                errors=[f"{type(exc).__name__}: {exc}"],
                input_summary={
                    "fixture": request.dataset_name,
                    "row_count": len(request.rows),
                    "runner": method.method_type,
                    "sandbox_provider": self.name,
                    "network_disabled": request.network_disabled,
                    "real_database_used": False,
                },
            )
