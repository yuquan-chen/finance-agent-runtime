from __future__ import annotations

from finance_agent.harness.analysis_schema import MethodDraft, MockDryRunResult
from finance_agent.sandbox.local_provider import LocalProcessSandboxProvider
from finance_agent.sandbox.provider import SandboxExecutionRequest, SandboxProvider


DEFAULT_SANDBOX_PROVIDER = LocalProcessSandboxProvider()


def run_method_in_sandbox(
    method: MethodDraft,
    rows: list[dict],
    fixture_name: str,
    provider: SandboxProvider | None = None,
    extra_tables: dict[str, list[dict]] | None = None,
) -> MockDryRunResult:
    sandbox_provider = provider or DEFAULT_SANDBOX_PROVIDER
    request = SandboxExecutionRequest(
        method=method,
        rows=rows,
        dataset_name=fixture_name,
        extra_tables=extra_tables or {},
    )
    return sandbox_provider.execute(request)
