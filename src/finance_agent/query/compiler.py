from __future__ import annotations

from typing import Any

from finance_agent.harness.analysis_schema import AnalysisPlan, MethodDraft
from finance_agent.methods.generator import generate_method_drafts
from finance_agent.operations.handler_registry import OperationHandlerRegistry
from finance_agent.query.contracts import CompiledQuery


def compile_analysis_plan(
    plan: AnalysisPlan,
    registry: OperationHandlerRegistry | None = None,
    *,
    params: dict[str, Any] | None = None,
) -> list[CompiledQuery]:
    """Compile an analysis plan without changing private input semantics."""
    methods = generate_method_drafts(plan, registry)
    bound_params = dict(params or {})
    return [
        compile_method(method.model_copy(update={"params": bound_params}))
        for method in methods
    ]


def compile_method(method: MethodDraft) -> CompiledQuery:
    """Wrap a legacy method draft in the canonical compiler contract."""
    return CompiledQuery.from_method(method)
