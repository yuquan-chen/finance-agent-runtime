from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    question: str
    session_id: str | None = None
    skill_id: str | None = None


class MethodReviewRevisionRequest(BaseModel):
    instruction: str


class FrontendEventRequest(BaseModel):
    event: str
    session_id: str | None = None
    request_id: str | None = None
    status: str | None = None
    detail: str | None = None


class RunResponse(BaseModel):
    request_id: str
    session_id: str | None = None
    review_id: str | None = None
    status: str
    answer: str | None = None
    errors: list[str] = []
    result_ref: str | None = None
    plan_result_ref: str | None = None
    result_refs: list[str] | None = None
    referenced_result_ref: str | None = None
    public_memory_entry: dict[str, Any] | None = None
    public_memory_context: list[dict[str, Any]] | None = None
    response_plan: dict[str, Any] | None = None
    action_validation: dict[str, Any] | None = None
    selected_skill_detail: dict[str, Any] | None = None
    skill_card: dict[str, Any] | None = None
    schema_candidates: list[dict[str, Any]] | None = None
    selected_schema_tables: list[str] | None = None
    metadata_disclosure: dict[str, Any] | None = None
    tool_decision: dict[str, Any] | None = None
    planner_used: str | None = None
    sql: str | None = None
    row_count: int | None = None
    analysis_plan: dict[str, Any] | None = None
    analysis_plan_review_card: dict[str, Any] | None = None
    method_draft: dict[str, Any] | None = None
    method_drafts: list[dict[str, Any]] | None = None
    harness_review: dict[str, Any] | None = None
    harness_reviews: list[dict[str, Any]] | None = None
    mock_result: dict[str, Any] | None = None
    mock_results: list[dict[str, Any]] | None = None
    internal_method_review: dict[str, Any] | None = None
    method_review_card: dict[str, Any] | None = None
    method_review_cards: list[dict[str, Any]] | None = None
    method_set_review_card: dict[str, Any] | None = None
    data_authorization_card: dict[str, Any] | None = None
    prior_result_authorization_card: dict[str, Any] | None = None
    execution_result_card: dict[str, Any] | None = None
    execution_result_cards: list[dict[str, Any]] | None = None
    result_narration: dict[str, Any] | None = None
    result_narrations: list[dict[str, Any]] | None = None
    audit: dict[str, Any] | None = None


class SessionCreateRequest(BaseModel):
    title: str | None = None


class SessionResponse(BaseModel):
    session_id: str
    title: str
    created_at: str
    updated_at: str
    pinned: bool = False
    message_count: int = 0


class SkillStateRequest(BaseModel):
    state: dict[str, Any]


class SkillSessionOpenRequest(BaseModel):
    skill_id: str | None = None


class SkillAgentMessageRequest(BaseModel):
    message: str = ""
    attachment_ids: list[str] = Field(default_factory=list)


class KycOcrRequest(BaseModel):
    upload_id: str


class KycAttachmentProcessRequest(BaseModel):
    attachment_ids: list[str]
    message: str | None = None
    requested_skill_id: str | None = None


class AttachmentIntentRequest(BaseModel):
    attachment_ids: list[str]
    message: str | None = None
    requested_skill_id: str | None = None


class KycAttachmentConfirmRequest(BaseModel):
    upload_id: str | None = None
    field_ids: list[str] = Field(default_factory=list)
