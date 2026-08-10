from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from finance_agent.harness.analysis_schema import MethodDraft, MockDryRunResult


@dataclass(frozen=True)
class SandboxExecutionRequest:
    method: MethodDraft
    rows: list[dict[str, Any]]
    dataset_name: str
    run_id: str | None = None
    network_disabled: bool = True
    timeout_seconds: int = 30
    memory_mib: int = 256
    vcpu_count: int = 1
    extra_tables: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class SandboxProvider(Protocol):
    name: str

    def execute(self, request: SandboxExecutionRequest) -> MockDryRunResult:
        """Execute a method in a sandbox provider."""

