from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from finance_agent.chat.response_plan import (
    ResponsePlan,
    plan_response_with_llm,
)
from finance_agent.config import Settings
from finance_agent.llm.provider import LlmProvider

ResponseMode = Literal["chat_response", "help_response", "clarification", "refusal", "tool_call"]


class ToolDecision(BaseModel):
    response_mode: ResponseMode
    tool_name: str | None = None
    assistant_message: str = ""
    reason: str = ""
    confidence: float = 1.0
    safety_flags: list[str] = Field(default_factory=list)
    tool_arguments: dict[str, Any] = Field(default_factory=dict)


def decide_tool_use_with_llm(message: str, settings: Settings, llm_provider: LlmProvider) -> ToolDecision:
    plan = plan_response_with_llm(message, settings, llm_provider)
    return response_plan_to_tool_decision(plan)


def decide_tool_use(message: str) -> ToolDecision:
    raise NotImplementedError("decide_tool_use 不再支持无 LLM 模式，请使用 decide_tool_use_with_llm")


def response_plan_to_tool_decision(plan: ResponsePlan) -> ToolDecision:
    if plan.refused:
        return ToolDecision(
            response_mode="refusal",
            assistant_message=plan.message,
            confidence=plan.confidence,
            safety_flags=list(plan.safety_flags),
        )
    proposal = plan.method_proposal
    if proposal and proposal.goal:
        # Native Skill calls expose their registered business entrypoint. Keep
        # the legacy analysis name only for proposals from the old contract.
        tool_name = (
            proposal.entity_id
            if proposal.entity_type == "skill" and proposal.entity_id
            else "analysis.prepare_method"
        )
        return ToolDecision(
            response_mode="tool_call",
            tool_name=tool_name,
            assistant_message=plan.message,
            reason=proposal.reason,
            confidence=plan.confidence,
            tool_arguments={
                "user_goal": proposal.goal,
                "entity_id": proposal.entity_id,
                "result_refs": proposal.result_refs,
                "params": proposal.params,
            },
        )
    return ToolDecision(
        response_mode="chat_response",
        assistant_message=plan.message,
        confidence=plan.confidence,
    )
