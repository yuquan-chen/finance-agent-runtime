from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    request_id: str
    user_query: str
    status: str
    errors: list[str]
    public_memory_context: list[dict[str, Any]]
    public_memory_entry: dict[str, Any]
    result_ref: str
    response_plan: dict[str, Any]
    action_validation: dict[str, Any]
    selected_skill_detail: dict[str, Any]
    tool_decision: dict[str, Any]
    action_user_goal: str
    visible_catalog: dict[str, Any]
    raw_plan: dict[str, Any]
    validated_plan: dict[str, Any]
    analysis_plan: dict[str, Any]
    analysis_plan_review_card: dict[str, Any]
    method_draft: dict[str, Any]
    method_drafts: list[dict[str, Any]]
    harness_review: dict[str, Any]
    harness_reviews: list[dict[str, Any]]
    mock_result: dict[str, Any]
    mock_results: list[dict[str, Any]]
    internal_method_review: dict[str, Any]
    repair_attempts: int
    repair_history: list[dict[str, Any]]
    method_review_card: dict[str, Any]
    method_review_cards: list[dict[str, Any]]
    data_authorization_card: dict[str, Any]
    execution_result_card: dict[str, Any]
    execution_result_cards: list[dict[str, Any]]
    result_narration: dict[str, Any]
    result_narrations: list[dict[str, Any]]
    planner_used: str
    sql: str
    rows: list[dict[str, Any]]
    row_count: int
    elapsed_ms: int
    answer: str
    audit: dict[str, Any]
    # Dependent execution fields
    referenced_result_ref: str
    referenced_result_refs: list[str]
    referenced_result_data: list[dict[str, Any]]
    referenced_result_tables: dict[str, list[dict[str, Any]]]
    prior_result_schema: dict[str, Any]
    prior_result_schemas: list[dict[str, Any]]
    prior_result_authorization_card: dict[str, Any]
    # Memory fields
    sent_memory_count: int
    relevant_memories: list[dict[str, Any]]
    public_memory_entries: list[dict[str, Any]]
    # SQL fields
    completed_sql: str
