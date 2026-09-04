"""Side-thread execution with safe parent snapshots and explicit handoffs."""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from finance_agent.kyc.attachment_ingest import extract_attachment_reviews
from finance_agent.kyc.conversation import update_from_conversation
from finance_agent.session.manager import SessionManager
from finance_agent.session.thread_store import RESUMABLE_STATUSES, ThreadStoreError, WorkflowConflictError
from finance_agent.skills.registry import SkillRegistry


class SkillAgentError(ValueError):
    """侧边 Skill Agent 请求错误。"""


GENERAL_AGENT_ID = "general"
GENERAL_HANDLER_ID = "general"
STRUCTURED_FORM_HANDLER_ID = "structured_form"
GENERAL_HISTORY_MAX_MESSAGES = 4
GENERAL_HISTORY_MAX_CHARS = 2400


@dataclass
class SideAgentTurn:
    """Result returned by a side-agent handler before the session is persisted."""

    answer: str
    state: dict[str, Any]
    uncertain: list[dict[str, Any]] = field(default_factory=list)
    reviews: list[dict[str, Any]] = field(default_factory=list)


SideAgentHandler = Callable[
    [dict[str, Any], Any, str, list[dict[str, Any]], dict[str, Any], str],
    SideAgentTurn,
]


@dataclass(frozen=True)
class SideAgentHandlerRegistration:
    handler: SideAgentHandler
    attachment_access: str = "metadata"


class SkillAgentExecutor:
    """创建、恢复并执行绑定到主会话的 Skill 子会话。"""

    def __init__(
        self,
        *,
        session_manager: SessionManager,
        skill_registry: SkillRegistry,
        llm_provider: Any,
    ):
        self.session_manager = session_manager
        self.skill_registry = skill_registry
        self.llm_provider = llm_provider
        self._handlers: dict[str, SideAgentHandlerRegistration] = {
            GENERAL_HANDLER_ID: SideAgentHandlerRegistration(self._respond_general),
            STRUCTURED_FORM_HANDLER_ID: SideAgentHandlerRegistration(
                self._respond_structured_form,
                attachment_access="ocr",
            ),
        }

    def register_handler(
        self,
        handler_id: str,
        handler: SideAgentHandler,
        *,
        attachment_access: str = "metadata",
    ) -> None:
        """Register a side-agent handler for future Skill configurations.

        A handler receives only the bound child session, its Skill definition,
        selected parent-owned attachments, and the scoped shared state. By
        default it receives attachment metadata only. ``ocr`` access is
        reserved for handlers that explicitly need approved extraction input.
        It does not get a route into the main query/execution graph.
        """
        normalized = str(handler_id or "").strip()
        if not normalized:
            raise ValueError("side-agent handler id is required")
        if normalized in self._handlers:
            raise ValueError(f"side-agent handler already registered: {normalized}")
        if attachment_access not in {"metadata", "ocr"}:
            raise ValueError("side-agent attachment access must be metadata or ocr")
        self._handlers[normalized] = SideAgentHandlerRegistration(handler, attachment_access)

    def _handler_id(self, skill, skill_session: dict[str, Any] | None = None) -> str:
        persisted = (skill_session or {}).get("handler_id")
        configured = getattr(skill, "side_agent_handler", "") if skill is not None else ""
        # Old sessions/configs retain their existing behaviour during rollout.
        fallback = (
            STRUCTURED_FORM_HANDLER_ID
            if skill is not None and skill.card.get("type") in {"intake", "identity"}
            else GENERAL_HANDLER_ID
        )
        handler_id = str(persisted or configured or fallback)
        if handler_id not in self._handlers:
            raise SkillAgentError(f"side-agent handler not registered: {handler_id}")
        return handler_id

    @staticmethod
    def _attachments_for_handler(
        attachments: list[dict[str, Any]],
        attachment_access: str,
    ) -> list[dict[str, Any]]:
        if attachment_access == "ocr":
            return attachments
        return [
            {
                key: attachment.get(key)
                for key in (
                    "document_id",
                    "name",
                    "size",
                    "type",
                    "uploaded_at",
                    "ocr_status",
                    "ocr_message",
                )
                if attachment.get(key) is not None
            }
            for attachment in attachments
        ]

    def _skill(self, skill_id: str):
        skill = self.skill_registry.resolve(skill_id)
        if skill is None:
            raise SkillAgentError(f"skill not registered: {skill_id}")
        if not skill.card:
            raise SkillAgentError(f"skill has no workflow card: {skill.name}")
        return skill

    def _context(self, parent_session_id: str) -> dict[str, Any]:
        """Build a bounded parent snapshot without forwarding chat transcripts.

        Parent messages may carry account identifiers, amounts, or other values
        that are permitted in the main workflow but not in a generic side chat.
        The snapshot therefore exposes only fixed, safe workflow indicators.
        """
        pending_review = self.session_manager.get_pending_review(parent_session_id) or {}
        return {
            "version": 1,
            "parent_session_id": parent_session_id,
            "scope": "绑定主会话的受控侧边线程",
            "parent_workflow": {
                "has_pending_review": bool(pending_review),
                "review_status": str(pending_review.get("status") or "none"),
            },
            "policy": "不包含主聊天原文、查询参数、查询结果、私有分析或附件正文。",
        }

    def _general_messages(
        self,
        skill_session: dict[str, Any],
        skill,
        message: str,
        attachment_context: str = "",
    ) -> list[dict[str, str]]:
        skill_context = ""
        if skill is not None:
            skill_context = (
                f"\n当前绑定 Skill：{skill.title or skill.name}\n"
                f"Skill 说明：{skill.description or '无'}\n"
                "具体草稿字段由结构化工作流处理，通用侧边聊天不可读取。\n"
            )
        system = (
            "你是 Finance Agent 的侧边聊天 Agent。你只拥有当前侧边线程的消息和"
            "创建时生成的安全主会话快照。不要假设自己看过主聊天原文。"
            "你可以解释、总结、提出下一步建议；不要声称已经执行数据库查询、修改文件或完成外部操作。"
            "需要执行主 Agent 才能完成的动作时，明确告诉用户回到主聊天确认。"
            "回答使用中文，简洁但要有实质内容。"
            + skill_context
        )
        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        messages.append(
            {
                "role": "user",
                "content": "以下是创建侧边线程时的安全主会话快照，仅用于理解工作状态：\n"
                + json.dumps(skill_session.get("context_snapshot") or skill_session.get("context") or {}, ensure_ascii=False),
            }
        )
        history: list[dict[str, str]] = []
        history_chars = 0
        for item in reversed(skill_session.get("messages") or []):
            role = item.get("role")
            content = str(item.get("content") or "").strip()
            if role not in {"user", "assistant"} or not content:
                continue
            content = content[:1000]
            if history and history_chars + len(content) > GENERAL_HISTORY_MAX_CHARS:
                break
            history.append({"role": role, "content": content})
            history_chars += len(content)
            if len(history) >= GENERAL_HISTORY_MAX_MESSAGES:
                break
        messages.extend(reversed(history))
        user_content = message or "请处理我上传的附件。"
        if attachment_context:
            user_content += "\n\n以下是附件元数据；附件正文不会提供给通用侧边聊天：\n" + attachment_context
        messages.append({"role": "user", "content": user_content})
        return messages

    def _opening_message(self, skill_session: dict[str, Any], skill) -> str:
        """Return a fixed opening notice so opening the panel does not spend model tokens."""
        if skill is None:
            return "侧边助手已打开。这里与主聊天独立；请直接说明需要协助的事项。"
        title = skill.card.get("title") or skill.title or skill.name
        return f"已打开「{title}」。请继续提供需要填写、核对或确认的信息。"

    def _skill_state_message(
        self,
        *,
        skill_session: dict[str, Any],
        skill,
        user_message: str,
        state: dict[str, Any],
        updates: dict[str, Any],
        uncertain: list[dict[str, Any]],
        reviews: list[dict[str, Any]],
    ) -> str | None:
        """Let the model narrate the current workflow state for the user."""
        if not callable(getattr(self.llm_provider, "chat", None)):
            return None
        payload = {
            "user_message": user_message,
            "skill_title": skill.title or skill.name,
            "field_updates": updates,
            "uncertain_fields": uncertain,
            "attachment_reviews": reviews,
            "current_state": state,
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "你是 Finance Agent 的工作流侧边助手。根据给出的实时事件和当前状态，"
                    "生成一条简洁、自然的中文回复。自行判断应该说明正在做什么、已经记录了什么、"
                    "还缺什么，以及是否需要用户确认或辅助。OCR 结果只能作为待确认证据，"
                    "不要声称已经写入草稿，除非事件明确表示已确认。不得猜测、编造、输出 JSON、"
                    "内部字段 id 或固定示例。"
                ),
            },
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        try:
            response = self.llm_provider.chat(messages, temperature=0.2, max_tokens=800)
            answer = str(response.content or "").strip()
            return answer or None
        except Exception:
            return None

    @staticmethod
    def _welcome(skill) -> str:
        title = skill.card.get("title") or skill.name
        return f"已进入「{title}」填写模式。你可以直接用自然语言提供信息，我会按当前阶段记录，并保留卡片供你核对。"

    def _snapshot(self, skill_session: dict[str, Any], skill) -> dict[str, Any]:
        state_key = skill_session.get("state_key") or (skill.name if skill is not None else GENERAL_AGENT_ID)
        state, revision = self.session_manager.get_skill_state_with_revision(
            skill_session["parent_session_id"], state_key
        )
        side_attachment_ids = {
            str(attachment.get("document_id"))
            for message in (skill_session.get("messages") or [])
            for attachment in (message.get("attachments") or [])
            if attachment.get("document_id")
        }
        attachment_reviews = [
            review
            for review in (state.get("pending_attachment_reviews") or {}).values()
            if isinstance(review, dict)
            and (
                review.get("surface") == "side"
                or str(review.get("attachment_id")) in side_attachment_ids
            )
        ]
        return {
            "skill_session": skill_session,
            "skill_id": skill.name if skill is not None else GENERAL_AGENT_ID,
            "skill_detail": skill.detail_spec() if skill is not None else {
                "skill_id": GENERAL_AGENT_ID,
                "title": "侧边聊天",
                "description": "理解当前主会话并协助推进任务",
            },
            "skill_card": skill.card if skill is not None else None,
            "state": state,
            "workflow_revision": revision,
            "attachment_reviews": attachment_reviews,
            "upload_options": [
                {"id": item.get("id"), "label": item.get("label") or item.get("id")}
                for item in ((skill.card if skill is not None else {}) or {}).get("uploads", [])
                if item.get("id")
            ],
        }

    def _respond_structured_form(
        self,
        skill_session: dict[str, Any],
        skill,
        message: str,
        attachments: list[dict[str, Any]],
        current: dict[str, Any],
        state_key: str,
    ) -> SideAgentTurn:
        """Handle a confirmed-field workflow without entering the main graph."""
        if skill is None or skill.card.get("type") not in {"intake", "identity"}:
            raise SkillAgentError("structured_form handler requires an intake or identity card")
        state = current
        uncertain: list[dict[str, Any]] = []
        reviews: list[dict[str, Any]] = []
        answer_parts: list[str] = []
        updates: dict[str, Any] = {}
        if message:
            try:
                result = update_from_conversation(
                    message=message,
                    card=skill.card,
                    state=state,
                    provider=self.llm_provider,
                )
                updates = result["updates"]
                state = {
                    **state,
                    "fields": {**(state.get("fields") or {}), **updates},
                }
                answer_parts.append(result["message"])
                uncertain = result.get("uncertain", [])
            except Exception:
                answer_parts.append(
                    "这句话暂时无法可靠映射到当前字段，请直接填写卡片，或换一种方式描述。"
                )
        if attachments:
            try:
                reviews = extract_attachment_reviews(
                    card=skill.card,
                    attachments=attachments,
                    provider=self.llm_provider,
                )
            except Exception:
                reviews = [
                    {
                        "attachment_id": item["document_id"],
                        "filename": item.get("name") or "材料",
                        "ocr_status": item.get("ocr_status"),
                        "ocr_message": item.get("ocr_message"),
                        "suggested_upload_id": None,
                        "confidence": 0,
                        "field_candidates": [],
                        "status": "pending_confirmation",
                    }
                    for item in attachments
                ]
            pending = dict(state.get("pending_attachment_reviews") or {})
            reviews = [
                {
                    **review,
                    "surface": "side",
                    "skill_session_id": skill_session["skill_session_id"],
                }
                for review in reviews
            ]
            pending.update({review["attachment_id"]: review for review in reviews})
            state = {**state, "pending_attachment_reviews": pending}
            completed = sum(1 for item in attachments if item.get("ocr_status") == "completed")
            answer_parts.append(
                f"已收到 {len(attachments)} 份材料，{completed} 份已完成本地 OCR。"
                "识别结果已整理为待确认候选，不会自动写入 KYC 草稿。"
            )
        answer = self._skill_state_message(
            skill_session=skill_session,
            skill=skill,
            user_message=message,
            state=state,
            updates=updates,
            uncertain=uncertain,
            reviews=reviews,
        ) or "\n\n".join(part for part in answer_parts if part)
        return SideAgentTurn(
            answer=answer or "请继续提供当前步骤的信息，或上传需要识别的材料。",
            state=state,
            uncertain=uncertain,
            reviews=reviews,
        )

    def _respond_general(
        self,
        skill_session: dict[str, Any],
        skill,
        message: str,
        attachments: list[dict[str, Any]],
        current: dict[str, Any],
        _state_key: str,
    ) -> SideAgentTurn:
        """Handle a read-only conversational helper with no workflow writes."""
        # General side chat never receives OCR body text. Workflows that need
        # field extraction must opt into the structured-form handler instead.
        attachment_context = "\n\n".join(
            f"[{item.get('name') or '材料'}]\nOCR 状态: {item.get('ocr_status') or 'unknown'}"
            for item in attachments
        )
        response = self.llm_provider.chat(
            self._general_messages(skill_session, skill, message, attachment_context),
            temperature=0.2,
            max_tokens=400,
        )
        return SideAgentTurn(
            answer=response.content.strip() or "我暂时没有生成有效回复，请换一种方式描述。",
            state=current,
        )

    def open(self, parent_session_id: str, skill_id: str | None = None) -> dict[str, Any]:
        if self.session_manager.get_session(parent_session_id) is None:
            raise SkillAgentError("parent session not found")
        normalized_skill_id = skill_id or GENERAL_AGENT_ID
        skill = None if normalized_skill_id == GENERAL_AGENT_ID else self._skill(normalized_skill_id)
        handler_id = self._handler_id(skill)
        sessions = self.session_manager.list_skill_sessions(parent_session_id)
        current = next(
            (
                item
                for item in sessions
                if item.get("skill_id") == normalized_skill_id and item.get("status") in RESUMABLE_STATUSES
            ),
            None,
        )
        if current:
            skill_session = self.session_manager.get_skill_session(
                current["skill_session_id"], parent_session_id=parent_session_id
            ) or current
        else:
            skill_session = self.session_manager.create_skill_session(
                parent_session_id,
                normalized_skill_id,
                state_key=(skill.card.get("state_key") if skill is not None else GENERAL_AGENT_ID)
                or normalized_skill_id,
                handler_id=handler_id,
                context=self._context(parent_session_id),
            )
            if skill_session is None:
                raise SkillAgentError("unable to create skill session")
            self.session_manager.add_skill_session_message(
                skill_session["skill_session_id"],
                "assistant",
                self._opening_message(skill_session, skill),
            )
            skill_session = self.session_manager.get_skill_session(skill_session["skill_session_id"]) or skill_session
        return self._snapshot(skill_session, skill)

    def messages(self, skill_session_id: str) -> dict[str, Any]:
        skill_session = self.session_manager.get_skill_session(skill_session_id)
        if skill_session is None:
            raise SkillAgentError("skill session not found")
        skill = None if skill_session["skill_id"] == GENERAL_AGENT_ID else self._skill(skill_session["skill_id"])
        return self._snapshot(skill_session, skill)

    def respond(
        self,
        skill_session_id: str,
        message: str,
        attachment_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        message = (message or "").strip()
        requested_attachment_ids = list(
            dict.fromkeys(str(item) for item in (attachment_ids or []) if item)
        )
        if not message and not requested_attachment_ids:
            raise SkillAgentError("message or attachment is required")
        skill_session = self.session_manager.get_skill_session(skill_session_id)
        if skill_session is None:
            raise SkillAgentError("skill session not found")
        if skill_session.get("status") not in RESUMABLE_STATUSES:
            raise SkillAgentError("skill session is not resumable")
        skill = None if skill_session["skill_id"] == GENERAL_AGENT_ID else self._skill(skill_session["skill_id"])
        parent_id = skill_session["parent_session_id"]
        state_key = skill_session.get("state_key") or (skill.name if skill is not None else GENERAL_AGENT_ID)
        current, state_revision = self.session_manager.get_skill_state_with_revision(parent_id, state_key)

        attachment_map = {
            str(item.get("document_id")): item
            for item in self.session_manager.get_attachments(parent_id)
            if item.get("document_id")
        }
        attachments = [
            attachment_map[item]
            for item in requested_attachment_ids
            if item in attachment_map
        ]
        if len(attachments) != len(requested_attachment_ids):
            raise SkillAgentError("部分附件不存在或不属于当前主会话")

        registration = self._handlers[self._handler_id(skill, skill_session)]
        handler_attachments = self._attachments_for_handler(attachments, registration.attachment_access)
        try:
            self.session_manager.begin_skill_session_turn(skill_session_id)
            turn = registration.handler(skill_session, skill, message, handler_attachments, current, state_key)
        except Exception as error:
            try:
                self.session_manager.fail_skill_session_turn(skill_session_id, "handler_error")
            except ThreadStoreError:
                pass
            if isinstance(error, SkillAgentError):
                raise
            raise SkillAgentError("side-agent handler failed") from error
        answer = turn.answer
        state = turn.state
        uncertain = turn.uncertain
        reviews = turn.reviews

        stored_content = message or "已上传附件"
        if attachments:
            stored_content += "\n\n[已上传材料] " + "、".join(
                str(item.get("name") or "材料") for item in attachments
            )
        stored_attachments = [
            {
                key: item.get(key)
                for key in (
                    "document_id",
                    "name",
                    "size",
                    "type",
                    "uploaded_at",
                    "ocr_status",
                    "ocr_message",
                )
                if item.get(key) is not None
            }
            for item in attachments
        ]
        next_status = "waiting_confirmation" if reviews else "waiting_user"
        try:
            updated = self.session_manager.complete_skill_session_turn(
                skill_session_id=skill_session_id,
                user_content=stored_content,
                attachments=stored_attachments,
                answer=answer,
                state_key=state_key,
                state=state,
                expected_state_revision=state_revision,
                next_status=next_status,
            )
        except WorkflowConflictError as error:
            raise SkillAgentError("共享草稿已被其他操作更新，请刷新后重试") from error
        except ThreadStoreError as error:
            raise SkillAgentError(str(error)) from error
        return {
            **self._snapshot(updated, skill),
            "answer": answer,
            "uncertain": uncertain,
            "reviews": reviews,
            "attachments": attachments,
        }
