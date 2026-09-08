from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, Field

from finance_agent.harness.analysis_schema import HarnessReview, MethodDraft, MockDryRunResult


class QueryRequest(BaseModel):
    """The single internal request shape after LLM routing.

    Filter values deliberately do not live here. They remain in the private
    parameter binder and are attached only after SQL planning has completed.
    """

    goal: str
    filters: list[dict[str, Any]] = Field(default_factory=list)
    requested_metrics: list[str] = Field(default_factory=list)
    requested_dimensions: list[str] = Field(default_factory=list)
    history_reference: dict[str, Any] | None = None
    skill_id: str | None = None

    @classmethod
    def from_proposal(
        cls,
        proposal: Mapping[str, Any] | None,
        *,
        goal: str,
    ) -> QueryRequest:
        proposal = proposal or {}
        reference = proposal.get("query_reference")
        if hasattr(reference, "model_dump"):
            reference = reference.model_dump(mode="json")
        return cls(
            goal=goal,
            filters=[item for item in proposal.get("filter_specs", []) if isinstance(item, dict)],
            history_reference=reference if isinstance(reference, dict) and reference.get("mode") != "none" else None,
            skill_id=proposal.get("entity_id") if proposal.get("entity_type") == "skill" else None,
        )


class CompiledQuery(BaseModel):
    """A query ready for validation and execution.

    ``method`` is a compatibility payload for the existing executors. The
    surrounding fields are the stable compiler contract and are what new
    runtime components should consume.
    """

    goal: str
    operation: str
    table: str
    tables: list[str] = Field(default_factory=list)
    fields: list[str] = Field(default_factory=list)
    sql_template: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    result_schema: dict[str, str] = Field(default_factory=dict)
    data_source: Literal["table", "result_ref"] = "table"
    method: MethodDraft

    @classmethod
    def from_method(cls, method: MethodDraft) -> CompiledQuery:
        tables = [method.table]
        for field in method.required_fields:
            table = field.split(".", 1)[0]
            if table not in tables:
                tables.append(table)
        return cls(
            goal=method.goal,
            operation=method.operation,
            table=method.table,
            tables=tables,
            fields=list(method.required_fields),
            sql_template=method.sql_template,
            params=dict(method.params),
            result_schema=dict(method.output_schema),
            data_source=method.data_source,
            method=method,
        )


class ValidationReport(BaseModel):
    """One public runtime result for all deterministic query checks."""

    status: Literal["passed", "failed"]
    allowed: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    checks: list[str] = Field(default_factory=list)
    harness_reviews: list[HarnessReview] = Field(default_factory=list)
    mock_results: list[MockDryRunResult] = Field(default_factory=list)

    @property
    def harness_review(self) -> HarnessReview | None:
        return self.harness_reviews[0] if self.harness_reviews else None

    @property
    def mock_result(self) -> MockDryRunResult | None:
        return self.mock_results[0] if self.mock_results else None
