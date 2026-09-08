from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class AnalysisStep(BaseModel):
    operation: str
    table: str = "card_transaction"
    metric: str | None = None
    dimension: str | None = None
    group_by: str | None = None
    time_field: str | None = None
    grain: str | None = None
    limit: int | None = None
    filters: list[dict[str, Any]] = Field(default_factory=list)
    rationale: str = ""
    sql: str | None = None  # LLM 写的 SQL
    code: str | None = None  # LLM 写的 Python 代码

    @field_validator("operation")
    @classmethod
    def normalize_operation(cls, value: str) -> str:
        return value.strip().lower().replace(" ", "_")


class AnalysisPlan(BaseModel):
    mode: Literal["analysis_plan", "single_operation", "method_creation", "clarification", "refusal", "help_response"] = (
        "analysis_plan"
    )
    goal: str
    assumptions: list[str] = Field(default_factory=list)
    steps: list[AnalysisStep] = Field(default_factory=list)
    required_metadata: list[str] = Field(default_factory=list)
    requires_method_generation: bool = True
    rationale: str = ""


class MethodDraft(BaseModel):
    method_type: Literal["sql", "code"]
    name: str
    goal: str
    operation: str
    table: str = "card_transaction"
    data_source: Literal["table", "result_ref"] = "table"
    result_ref: str | None = None
    required_fields: list[str] = Field(default_factory=list)
    sql_template: str | None = None
    code: str | None = None
    parameters: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)  # SQL 参数值，如 {"customer_name": "Company 10"}
    output_schema: dict[str, str] = Field(default_factory=dict)
    risk_level: str = "low"
    logic_summary: list[str] = Field(default_factory=list)


class HarnessReview(BaseModel):
    allowed: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class MockDryRunResult(BaseModel):
    status: Literal["passed", "failed"]
    output: dict[str, Any] | list[dict[str, Any]] | None = None
    errors: list[str] = Field(default_factory=list)
    input_summary: dict[str, Any] = Field(default_factory=dict)


class MethodReviewCard(BaseModel):
    method_name: str
    method_type: str
    goal: str
    required_fields: list[str]
    logic_summary: list[str]
    mock_result: MockDryRunResult
    risk_level: str
    approval_required: bool = True


class MethodSetReviewCard(BaseModel):
    """一次确认所覆盖的方法集合；steps 保留每个方法的审查信息。"""

    method_name: str = "method_set"
    method_type: str = "method_set"
    goal: str
    steps: list[MethodReviewCard] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)
    logic_summary: list[str] = Field(default_factory=list)
    risk_level: str = "low"
    approval_required: bool = True


class DataAuthorizationCard(BaseModel):
    status: Literal["pending"]
    purpose: str
    method_name: str
    method_hash: str
    tables: list[str]
    fields: list[str]
    filters: list[dict[str, Any]] = Field(default_factory=list)
    row_limit: int
    readonly: bool = True
    real_data_read: bool = False
    safety_notes: list[str] = Field(default_factory=list)


class ExecutionResultCard(BaseModel):
    status: Literal["executed"]
    execution_mode: Literal["simulated_real", "direct_db"]
    method_name: str
    method_hash: str
    data_authorization: DataAuthorizationCard
    result: dict[str, Any] | list[dict[str, Any]]
    row_count: int
    evidence: dict[str, Any] = Field(default_factory=dict)
    real_database_used: bool = False


class PriorResultAuthorizationCard(BaseModel):
    status: Literal["pending"]
    purpose: str
    method_name: str
    method_hash: str
    referenced_result_ref: str
    prior_result_fields: list[str]
    prior_result_row_count: int
    operation: str
    readonly: bool = True
    new_database_access: bool = False
    safety_notes: list[str] = Field(default_factory=list)
