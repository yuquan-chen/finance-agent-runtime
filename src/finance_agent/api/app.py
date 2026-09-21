from __future__ import annotations

import hashlib
import json
import time
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse

from finance_agent import __version__
from finance_agent.api.routes.query import router as query_router
from finance_agent.api.routes.runs import router as runs_router
from finance_agent.api.routes.sessions import router as sessions_router
from finance_agent.api.schemas import (
    AttachmentIntentRequest,
    FrontendEventRequest,
    KycAttachmentConfirmRequest,
    KycAttachmentProcessRequest,
    KycOcrRequest,
    RunResponse,
    SessionCreateRequest,
    SessionResponse,
    SkillAgentMessageRequest,
    SkillSessionOpenRequest,
    SkillStateRequest,
)
from finance_agent.graph.runtime import FinanceAgentRuntime
from finance_agent.kyc.attachment_ingest import extract_attachment_reviews
from finance_agent.kyc.attachment_intent import route_attachment_intent
from finance_agent.kyc.local_drafts import KycDraftError
from finance_agent.query.safe_requests import SafeQueryRegistry
from finance_agent.security.principal import Principal, principal_from_headers
from finance_agent.session.thread_store import RESUMABLE_STATUSES
from finance_agent.skills.agent import SkillAgentError


@lru_cache(maxsize=1)
def runtime() -> FinanceAgentRuntime:
    return FinanceAgentRuntime()


app = FastAPI(title="Finance Agent Runtime", version=__version__)

PENDING_RUNS: dict[str, dict[str, Any]] = {}

PENDING_REVIEW_STATUSES = {
    "analysis_plan_review_ready",
    "method_review_ready",
    "data_authorization_pending",
    "prior_result_authorization_pending",
}
app.include_router(runs_router)
app.include_router(sessions_router)
app.include_router(query_router)


@lru_cache(maxsize=1)
def safe_query_registry() -> SafeQueryRegistry:
    return SafeQueryRegistry.from_yaml(runtime().settings.safe_query_definitions_path)


@app.post("/v1/frontend-events")
async def record_frontend_event(event: FrontendEventRequest) -> dict[str, str]:
    """Persist structural UI telemetry for diagnosing SSE/card rendering failures."""
    event_path = Path(runtime().settings.audit_log_path).with_name("frontend_events.jsonl")
    event_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": event.event[:80],
        "session_id": event.session_id,
        "request_id": event.request_id,
        "status": event.status,
        "detail": (event.detail or "")[:1000],
    }
    with event_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def chat_page() -> str:
    return (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "service": "finance-agent-runtime", "version": __version__}


@app.get("/v1/skills")
def list_skills() -> list[dict[str, Any]]:
    """返回前端可发现的 Skill manifest，不暴露表字段或业务数据。"""
    return runtime().skill_registry.manifest_for_llm()


def _canonical_skill_id(skill_id: str | None) -> str | None:
    if not skill_id:
        return None
    skill = runtime().skill_registry.resolve(skill_id)
    if skill is None:
        raise HTTPException(status_code=400, detail=f"skill not registered: {skill_id}")
    return skill.name


def _principal(request: Request) -> Principal:
    try:
        settings = runtime().settings
        return principal_from_headers(
            request.headers,
            auth_mode=settings.auth_mode,
            auth_secret=settings.auth_secret,
        )
    except ValueError as exc:
        if runtime().settings.auth_mode == "required":
            raise HTTPException(
                status_code=401,
                detail=str(exc),
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _require_session_access(session_id: str, principal: Principal) -> dict[str, Any]:
    manager = runtime().session_manager
    session = manager.get_session(session_id)
    if session is None or not manager.owns_session(
        session_id,
        user_id=principal.user_id,
        workspace_id=principal.workspace_id,
    ):
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def _require_skill_session_access(skill_session_id: str, principal: Principal) -> dict[str, Any]:
    skill_session = runtime().session_manager.get_skill_session(skill_session_id)
    if skill_session is None:
        raise HTTPException(status_code=404, detail="skill session not found")
    _require_session_access(str(skill_session["parent_session_id"]), principal)
    return skill_session


def _action_idempotency_key(
    request: Request,
    state: dict[str, Any],
    action: str,
    instruction: str | None = None,
) -> str:
    supplied = request.headers.get("x-idempotency-key")
    if supplied:
        return supplied[:256]
    review_id = str(state.get("review_id") or state.get("request_id") or "")
    if action == "method_review_revise":
        return hashlib.sha256(f"{review_id}:{instruction or ''}".encode()).hexdigest()
    return review_id


def _safe_action_response(state: dict[str, Any]) -> dict[str, Any]:
    """Persist only an idempotent response envelope, never result rows."""
    payload = _response_from_state(state).model_dump(mode="json")
    for key in ("mock_result", "mock_results", "public_memory_context"):
        payload.pop(key, None)

    def redact(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: redact(item)
                for key, item in value.items()
                if key not in {"result", "rows", "referenced_result_data"}
            }
        if isinstance(value, list):
            return [redact(item) for item in value]
        return value

    return redact(payload)


def _claim_action(
    request_id: str,
    *,
    action: str,
    state: dict[str, Any],
    principal: Principal,
    request: Request,
    instruction: str | None = None,
) -> tuple[str, str]:
    key = _action_idempotency_key(request, state, action, instruction)
    claim = runtime().run_store.claim_action(
        request_id,
        action=action,
        idempotency_key=key,
        user_id=principal.user_id,
        workspace_id=principal.workspace_id,
    )
    # Pending states created before RunStore was introduced can still be in
    # the process cache. Import a verified legacy state once before claiming.
    if claim.status == "not_found":
        runtime().run_store.save(state, _persistable_pending_state(state))
        claim = runtime().run_store.claim_action(
            request_id,
            action=action,
            idempotency_key=key,
            user_id=principal.user_id,
            workspace_id=principal.workspace_id,
        )
    if claim.status == "not_found":
        raise HTTPException(status_code=404, detail="run not found")
    if claim.status == "completed":
        raise _CompletedAction(claim.state or {})
    if claim.status == "in_progress":
        raise HTTPException(status_code=409, detail="该确认操作正在处理中，请勿重复提交")
    return action, key


class _CompletedAction(Exception):
    def __init__(self, payload: dict[str, Any]):
        self.payload = payload


@app.post("/api/clear-memory")
async def clear_public_memory(request: Request):
    """清空当前用户会话的模型可见记忆，但保留私有结果和会话历史。"""
    principal = _principal(request)
    session_ids = [
        session["session_id"]
        for session in runtime().session_manager.list_sessions(
            user_id=principal.user_id,
            workspace_id=principal.workspace_id,
        )
    ]
    cleared = sum(runtime().memory_store.delete_session(session_id) for session_id in session_ids)
    return {
        "status": "ok",
        "message": "模型可见记忆已清空",
        "memory_records": cleared,
    }


# ---------------------------------------------------------------------------
# Session 管理接口
# ---------------------------------------------------------------------------


# Session and side-agent routes live in api.routes.sessions.
async def list_sessions(request: Request):
    """列出当前用户和 workspace 的 session。"""
    principal = _principal(request)
    return runtime().session_manager.list_sessions(
        user_id=principal.user_id,
        workspace_id=principal.workspace_id,
    )


async def create_session(http_request: Request, request: SessionCreateRequest | None = None):
    """创建新的 session。"""
    principal = _principal(http_request)
    title = request.title if request else None
    session = runtime().session_manager.create_session(
        title,
        user_id=principal.user_id,
        workspace_id=principal.workspace_id,
    )
    return SessionResponse(
        session_id=session["session_id"],
        title=session["title"],
        created_at=session["created_at"],
        updated_at=session["updated_at"],
        pinned=bool(session.get("metadata", {}).get("pinned", False)),
        message_count=len(session.get("conversation_history", [])),
    )


async def get_session(session_id: str, request: Request):
    """获取 session 详情。"""
    session = _require_session_access(session_id, _principal(request))
    return SessionResponse(
        session_id=session["session_id"],
        title=session["title"],
        created_at=session["created_at"],
        updated_at=session["updated_at"],
        pinned=bool(session.get("metadata", {}).get("pinned", False)),
        message_count=len(session.get("conversation_history", [])),
    )


async def delete_session(session_id: str, request: Request):
    """删除 session 及其会话级记忆、私有结果和内存检查点。"""
    _require_session_access(session_id, _principal(request))
    deleted = await runtime().delete_session(session_id)
    if deleted is None:
        raise HTTPException(status_code=404, detail="Session not found")
    for key, state in list(PENDING_RUNS.items()):
        if key == session_id or state.get("session_id") == session_id:
            PENDING_RUNS.pop(key, None)
    return {"status": "ok", "message": "Session deleted", "deleted": deleted}


async def set_session_pinned(session_id: str, request: Request, pinned: bool = True):
    """置顶或取消置顶某个会话。"""
    _require_session_access(session_id, _principal(request))
    session = runtime().session_manager.set_session_pinned(session_id, pinned)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionResponse(
        session_id=session["session_id"],
        title=session["title"],
        created_at=session["created_at"],
        updated_at=session["updated_at"],
        pinned=bool(session.get("metadata", {}).get("pinned", False)),
        message_count=len(session.get("conversation_history", [])),
    )


async def get_session_history(session_id: str, request: Request, limit: int | None = None):
    """获取 session 的对话历史。"""
    principal = _principal(request)
    _require_session_access(session_id, principal)
    history = runtime().session_manager.get_conversation_history(session_id, limit)
    pending_review = runtime().session_manager.get_pending_review(session_id)
    persisted_state = runtime().session_manager.get_pending_run_state(session_id)
    if persisted_state and persisted_state.get("request_id"):
        PENDING_RUNS[persisted_state["request_id"]] = dict(persisted_state)
        PENDING_RUNS[session_id] = dict(persisted_state)
        # 升级前已有 pending_review 时也要补写其时间线卡片快照；否则
        # pending_review 本身存在，但刷新后的消息没有可挂载的确认卡。
        # 已完成/失败的运行也要经过同步，以清理升级前遗留的待确认状态。
        _sync_pending_review(persisted_state)
        pending_review = runtime().session_manager.get_pending_review(session_id)
    # 兼容本次升级前已在内存中等待确认的会话：首次读取历史时补写安全卡片。
    if pending_review is not None and pending_review.get("status") not in PENDING_REVIEW_STATUSES:
        runtime().session_manager.clear_review_snapshot(
            session_id,
            str(pending_review.get("request_id") or ""),
        )
        runtime().session_manager.set_pending_review(session_id, None)
        pending_review = None
    if pending_review is None:
        in_memory_state = PENDING_RUNS.get(session_id)
        if in_memory_state and in_memory_state.get("status") in PENDING_REVIEW_STATUSES:
            _sync_pending_review(in_memory_state)
            pending_review = runtime().session_manager.get_pending_review(session_id)
    kyc_state = runtime().session_manager.get_skill_state(session_id, "kyc_intake") or {}
    side_attachment_ids: set[str] = set()
    for side_summary in runtime().session_manager.list_skill_sessions(session_id):
        side_session = runtime().session_manager.get_skill_session(
            side_summary.get("skill_session_id"), parent_session_id=session_id
        )
        for message in (side_session or {}).get("messages", []):
            for attachment in message.get("attachments", []):
                if attachment.get("document_id"):
                    side_attachment_ids.add(str(attachment["document_id"]))
    pending_attachment_reviews = [
        review
        for review in (kyc_state.get("pending_attachment_reviews") or {}).values()
        if isinstance(review, dict)
        and review.get("surface", "main") != "side"
        and str(review.get("attachment_id")) not in side_attachment_ids
    ]
    kyc_card = runtime().skill_registry.get("kyc_intake")
    attachment_upload_options = [
        {"id": item.get("id"), "label": item.get("label") or item.get("id")}
        for item in ((kyc_card.card if kyc_card else {}) or {}).get("uploads", [])
        if item.get("id")
    ]
    return {
        "session_id": session_id,
        "history": history,
        "timeline": runtime().session_manager.get_timeline(session_id),
        "private_analysis": runtime().session_manager.get_private_analysis(session_id),
        "pending_review": pending_review,
        "attachment_reviews": pending_attachment_reviews,
        "attachment_upload_options": attachment_upload_options,
        "run_detail": _hydrate_current_skill_run_detail(
            runtime().session_manager.get_run_detail(session_id)
        ),
    }


async def get_skill_state(session_id: str, skill_key: str, request: Request):
    """读取当前会话中某个 Skill 的表单/草稿状态。"""
    _require_session_access(session_id, _principal(request))
    return {
        "session_id": session_id,
        "skill_key": skill_key,
        "state": runtime().session_manager.get_skill_state(session_id, skill_key) or {},
    }


async def put_skill_state(
    session_id: str,
    skill_key: str,
    request: SkillStateRequest,
    http_request: Request,
):
    """保存当前会话中某个 Skill 的表单/草稿状态。"""
    _require_session_access(session_id, _principal(http_request))
    existing = runtime().session_manager.get_skill_state(session_id, skill_key) or {}
    # 表单只提交自己管理的字段；OCR review、来源标记等运行时状态不能被覆盖。
    merged_state = {**existing, **request.state}
    saved = runtime().session_manager.set_skill_state(session_id, skill_key, merged_state)
    if saved is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "ok", "session_id": session_id, "skill_key": skill_key, "state": merged_state}


async def list_skill_sessions(session_id: str, request: Request):
    """列出当前主会话下可恢复的侧边 Skill Agent。"""
    _require_session_access(session_id, _principal(request))
    return {
        "session_id": session_id,
        "skill_sessions": runtime().session_manager.list_skill_sessions(session_id),
    }


async def open_skill_session(
    session_id: str,
    request: SkillSessionOpenRequest,
    http_request: Request,
):
    """打开或恢复通用侧边 Skill Agent。"""
    _require_session_access(session_id, _principal(http_request))
    skill_id = _canonical_skill_id(request.skill_id)
    try:
        return runtime().open_skill_agent(session_id, skill_id or request.skill_id)
    except SkillAgentError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


async def get_skill_session(skill_session_id: str, request: Request):
    """读取侧边 Agent 的独立消息、卡片和共享状态。"""
    _require_skill_session_access(skill_session_id, _principal(request))
    try:
        return runtime().get_skill_agent(skill_session_id)
    except SkillAgentError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


async def send_skill_session_message(
    skill_session_id: str,
    request: SkillAgentMessageRequest,
    http_request: Request,
):
    """向侧边 Agent 发消息；不会触发主聊天的财务查询链路。"""
    _require_skill_session_access(skill_session_id, _principal(http_request))
    try:
        return runtime().send_skill_agent_message(
            skill_session_id, request.message, request.attachment_ids
        )
    except SkillAgentError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail="Skill Agent 暂时无法处理这条消息") from error


async def upload_skill_session_attachment(skill_session_id: str, request: Request):
    """Upload a side Agent attachment into the parent session inbox and OCR it."""
    skill_session = _require_skill_session_access(skill_session_id, _principal(request))
    if skill_session.get("status") not in RESUMABLE_STATUSES:
        raise HTTPException(status_code=400, detail="skill session is not resumable")
    parent_id = skill_session["parent_session_id"]
    if runtime().session_manager.get_session(parent_id) is None:
        raise HTTPException(status_code=404, detail="parent session not found")
    content_length = request.headers.get("content-length")
    max_size_mb = 10
    if content_length and content_length.isdigit() and int(content_length) > max_size_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"文件不能超过 {max_size_mb} MB")
    try:
        document = runtime().kyc_drafts.save_inbox_upload(
            session_id=parent_id,
            filename=unquote(request.headers.get("x-file-name", "")),
            content_type=request.headers.get("content-type", ""),
            content=await request.body(),
            max_size_mb=max_size_mb,
        )
        if document.get("ocr_status") == "pending":
            try:
                document = runtime().kyc_drafts.run_ocr(
                    session_id=parent_id,
                    skill_key="chat_inbox",
                    record=document,
                )
            except KycDraftError as error:
                document = {**document, "ocr_status": "failed", "ocr_message": str(error)}
    except KycDraftError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    runtime().session_manager.add_attachment(parent_id, document)
    return {"status": "ok", "attachment": document}


async def close_skill_session(skill_session_id: str, request: Request):
    """关闭侧边 Agent；共享草稿保留，之后可以重新打开。"""
    _require_skill_session_access(skill_session_id, _principal(request))
    updated = runtime().session_manager.update_skill_session(
        skill_session_id, {"status": "closed"}
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="skill session not found")
    return {"status": "ok", "skill_session": updated}


def _kyc_card(skill_key: str) -> dict[str, Any]:
    skill = runtime().skill_registry.get(skill_key)
    card = skill.card if skill else {}
    if not card or card.get("type") not in {"intake", "identity"}:
        raise HTTPException(status_code=404, detail="KYC Skill not found")
    return card


def _kyc_upload_spec(skill_key: str, upload_id: str) -> dict[str, Any]:
    card = _kyc_card(skill_key)
    spec = next((item for item in card.get("uploads", []) if item.get("id") == upload_id), None)
    if spec is None:
        raise HTTPException(status_code=404, detail="KYC upload field not found")
    return spec


def _kyc_draft_completion(card: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    fields = state.get("fields") if isinstance(state.get("fields"), dict) else {}
    uploads = state.get("uploads") if isinstance(state.get("uploads"), dict) else {}
    missing_fields = []
    for field in card.get("fields", []):
        if not field.get("required"):
            continue
        value = fields.get(field.get("id"))
        complete = bool(value) if field.get("type") == "checkbox" else bool(str(value or "").strip())
        if not complete:
            missing_fields.append(field.get("label") or field.get("id"))
    missing_uploads = [
        upload.get("label") or upload.get("id")
        for upload in card.get("uploads", [])
        if upload.get("required") and not isinstance(uploads.get(upload.get("id")), dict)
    ]
    return {
        "complete": not missing_fields and not missing_uploads,
        "missing_fields": missing_fields,
        "missing_uploads": missing_uploads,
        "field_count": len(card.get("fields", [])) - len(missing_fields),
        "upload_count": len(uploads),
    }


@app.post("/v1/sessions/{session_id}/attachments")
async def upload_chat_attachment(session_id: str, request: Request):
    """Store a chat attachment in the session inbox and run local OCR."""
    _require_session_access(session_id, _principal(request))
    content_length = request.headers.get("content-length")
    max_size_mb = 10
    if content_length and content_length.isdigit() and int(content_length) > max_size_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"文件不能超过 {max_size_mb} MB")
    try:
        document = runtime().kyc_drafts.save_inbox_upload(
            session_id=session_id,
            filename=unquote(request.headers.get("x-file-name", "")),
            content_type=request.headers.get("content-type", ""),
            content=await request.body(),
            max_size_mb=max_size_mb,
        )
        if document.get("ocr_status") == "pending":
            try:
                document = runtime().kyc_drafts.run_ocr(
                    session_id=session_id,
                    skill_key="chat_inbox",
                    record=document,
                )
            except KycDraftError as error:
                document = {
                    **document,
                    "ocr_status": "failed",
                    "ocr_message": str(error),
                }
    except KycDraftError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    runtime().session_manager.add_attachment(session_id, document)
    return {"status": "ok", "attachment": document}


@app.get("/v1/sessions/{session_id}/attachments/{attachment_id}")
async def get_chat_attachment(session_id: str, attachment_id: str, request: Request):
    """Serve a session-owned attachment for image previews in chat messages."""
    _require_session_access(session_id, _principal(request))
    attachment = next(
        (
            item
            for item in runtime().session_manager.get_attachments(session_id)
            if str(item.get("document_id")) == attachment_id
        ),
        None,
    )
    if attachment is None:
        raise HTTPException(status_code=404, detail="附件不存在")
    try:
        path = runtime().kyc_drafts.stored_upload_path(
            session_id=session_id,
            skill_key="chat_inbox",
            record=attachment,
        )
    except KycDraftError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return FileResponse(
        path,
        media_type=attachment.get("type") or "application/octet-stream",
        filename=Path(attachment.get("name") or path.name).name,
    )


@app.post("/v1/sessions/{session_id}/attachment-intent")
async def route_chat_attachment_intent(
    session_id: str,
    request: AttachmentIntentRequest,
    http_request: Request,
):
    """Use conversation context and OCR evidence to route uploaded files."""
    _require_session_access(session_id, _principal(http_request))
    requested_ids = list(dict.fromkeys(request.attachment_ids))
    if not requested_ids:
        raise HTTPException(status_code=400, detail="至少需要一份聊天附件")
    attachment_map = {
        str(item.get("document_id")): item
        for item in runtime().session_manager.get_attachments(session_id)
        if item.get("document_id")
    }
    attachments = [attachment_map[item] for item in requested_ids if item in attachment_map]
    if len(attachments) != len(requested_ids):
        raise HTTPException(status_code=404, detail="部分聊天附件不存在")
    requested_skill_id = _canonical_skill_id(request.requested_skill_id)
    decision = route_attachment_intent(
        message=(request.message or "").strip(),
        conversation_history=runtime().session_manager.get_conversation_history(session_id),
        attachments=attachments,
        skill_manifest=runtime().skill_registry.manifest_for_llm(),
        provider=runtime().llm_provider,
        requested_skill_id=requested_skill_id,
    )
    # The intake endpoint records its own user/assistant messages after the
    # detailed material review. Other routes finish at this endpoint, so keep
    # their safe attachment event and clarification in the session history.
    if (decision.get("intent") or {}).get("intent") != "intake":
        user_content = (request.message or "已上传附件").strip()
        user_content += "\n\n[已上传材料] " + "、".join(
            str(item.get("name") or "材料") for item in attachments
        )
        runtime().session_manager.add_message(session_id, "user", user_content)
        runtime().session_manager.add_message(
            session_id,
            "assistant",
            str(decision.get("message") or "附件已保存。"),
        )
    return {
        "status": "attachment_intent_routed",
        "session_id": session_id,
        **decision,
    }


@app.post("/v1/sessions/{session_id}/kyc/{skill_key}/attachment-intake")
async def process_chat_attachments(
    session_id: str,
    skill_key: str,
    request: KycAttachmentProcessRequest,
    http_request: Request,
):
    """Classify OCR results and return candidates for explicit user confirmation."""
    _require_session_access(session_id, _principal(http_request))
    card = _kyc_card(skill_key)
    requested_ids = list(dict.fromkeys(request.attachment_ids))
    if not requested_ids:
        raise HTTPException(status_code=400, detail="至少需要一份聊天附件")
    attachment_map = {
        str(item.get("document_id")): item
        for item in runtime().session_manager.get_attachments(session_id)
        if item.get("document_id")
    }
    attachments = [attachment_map[item] for item in requested_ids if item in attachment_map]
    if len(attachments) != len(requested_ids):
        raise HTTPException(status_code=404, detail="部分聊天附件不存在")

    extraction_error = None
    try:
        reviews = extract_attachment_reviews(
            card=card,
            attachments=attachments,
            provider=runtime().llm_provider,
        )
    except Exception as error:
        extraction_error = str(error)
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

    state = runtime().session_manager.get_skill_state(session_id, skill_key) or {}
    pending = dict(state.get("pending_attachment_reviews") or {})
    for review in reviews:
        pending[review["attachment_id"]] = {**review, "surface": "main"}
    state = {**state, "pending_attachment_reviews": pending}
    runtime().session_manager.set_skill_state(session_id, skill_key, state)

    message = (request.message or "请处理我上传的 KYC 材料。").strip()
    user_content = message + "\n\n[已上传材料] " + "、".join(
        str(item.get("name") or "材料") for item in attachments
    )
    completed = sum(1 for item in attachments if item.get("ocr_status") == "completed")
    answer = f"已收到 {len(attachments)} 份材料，{completed} 份已完成本地 OCR。"
    if extraction_error:
        answer += "字段候选暂未生成，请检查本地模型连接后重试。"
    else:
        answer += "识别结果已整理为待确认候选，不会自动写入 KYC 草稿。"
    runtime().session_manager.add_message(session_id, "user", user_content)
    runtime().session_manager.add_message(session_id, "assistant", answer)
    return {
        "status": "attachment_review_ready",
        "session_id": session_id,
        "skill_id": skill_key,
        "user_message": user_content,
        "answer": answer,
        "attachments": attachments,
        "reviews": reviews,
        "upload_options": [
            {"id": item.get("id"), "label": item.get("label") or item.get("id")}
            for item in card.get("uploads", [])
            if item.get("id")
        ],
        "state": state,
        "extraction_error": extraction_error,
    }


@app.post("/v1/sessions/{session_id}/kyc/{skill_key}/attachment-reviews/{attachment_id}/confirm")
async def confirm_chat_attachment(
    session_id: str,
    skill_key: str,
    attachment_id: str,
    request: KycAttachmentConfirmRequest,
    http_request: Request,
):
    """Merge one reviewed attachment and its selected candidates into the draft."""
    _require_session_access(session_id, _principal(http_request))
    card = _kyc_card(skill_key)
    state = runtime().session_manager.get_skill_state(session_id, skill_key) or {}
    pending = dict(state.get("pending_attachment_reviews") or {})
    review = pending.get(attachment_id)
    if not isinstance(review, dict):
        raise HTTPException(status_code=404, detail="待确认材料不存在")
    target_upload_id = request.upload_id or review.get("suggested_upload_id")
    upload_specs = {item.get("id"): item for item in card.get("uploads", [])}
    if target_upload_id not in upload_specs:
        raise HTTPException(status_code=400, detail="请先确认这份材料对应的材料类型")
    attachment = next(
        (
            item
            for item in runtime().session_manager.get_attachments(session_id)
            if str(item.get("document_id")) == attachment_id
        ),
        None,
    )
    if not attachment:
        raise HTTPException(status_code=404, detail="材料附件不存在")
    uploads = dict(state.get("uploads") or {})
    if target_upload_id in uploads and uploads[target_upload_id].get("document_id") != attachment_id:
        raise HTTPException(status_code=409, detail="这个材料位置已经有其他文件")
    try:
        promoted = runtime().kyc_drafts.promote_upload(
            session_id=session_id,
            source_skill_key="chat_inbox",
            target_skill_key=skill_key,
            target_upload_id=target_upload_id,
            record=attachment,
        )
    except KycDraftError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    uploads[target_upload_id] = promoted
    selected_ids = set(request.field_ids or [item.get("field_id") for item in review.get("field_candidates", [])])
    fields = dict(state.get("fields") or {})
    for candidate in review.get("field_candidates", []):
        if candidate.get("field_id") in selected_ids:
            fields[candidate["field_id"]] = candidate.get("value")
    review = {**review, "status": "confirmed", "confirmed_upload_id": target_upload_id}
    pending[attachment_id] = review
    updated = {**state, "fields": fields, "uploads": uploads, "pending_attachment_reviews": pending}
    runtime().session_manager.set_skill_state(session_id, skill_key, updated)
    return {
        "status": "ok",
        "message": "材料和已选择的识别字段已写入 KYC 草稿。",
        "review": review,
        "state": updated,
    }


@app.post("/v1/sessions/{session_id}/kyc/{skill_key}/uploads/{upload_id}")
async def upload_kyc_document(session_id: str, skill_key: str, upload_id: str, request: Request):
    """Store a KYC document locally for this session; it is never sent to DogPay."""
    _require_session_access(session_id, _principal(request))
    spec = _kyc_upload_spec(skill_key, upload_id)
    max_size_mb = spec.get("max_size_mb") or 10
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > int(max_size_mb * 1024 * 1024):
        raise HTTPException(status_code=413, detail=f"文件不能超过 {max_size_mb} MB")
    try:
        document = runtime().kyc_drafts.save_upload(
            session_id=session_id,
            skill_key=skill_key,
            upload_id=upload_id,
            filename=unquote(request.headers.get("x-file-name", "")),
            content_type=request.headers.get("content-type", ""),
            content=await request.body(),
            accept=str(spec.get("accept") or ".jpg,.jpeg,.png,.pdf"),
            max_size_mb=max_size_mb,
        )
    except KycDraftError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    state = runtime().session_manager.get_skill_state(session_id, skill_key) or {}
    uploads = dict(state.get("uploads") or {})
    uploads[upload_id] = document
    state = {**state, "uploads": uploads}
    runtime().session_manager.set_skill_state(session_id, skill_key, state)
    return {"status": "ok", "document": document, "state": state}


@app.post("/v1/sessions/{session_id}/kyc/{skill_key}/ocr")
async def run_kyc_ocr(
    session_id: str,
    skill_key: str,
    request: KycOcrRequest,
    http_request: Request,
):
    """Run local Tesseract OCR and retain raw text for explicit human review."""
    _require_session_access(session_id, _principal(http_request))
    _kyc_upload_spec(skill_key, request.upload_id)
    state = runtime().session_manager.get_skill_state(session_id, skill_key) or {}
    uploads = dict(state.get("uploads") or {})
    document = uploads.get(request.upload_id)
    if not isinstance(document, dict):
        raise HTTPException(status_code=404, detail="请先上传材料")
    try:
        updated = runtime().kyc_drafts.run_ocr(
            session_id=session_id,
            skill_key=skill_key,
            record=document,
        )
    except KycDraftError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    uploads[request.upload_id] = updated
    state = {**state, "uploads": uploads}
    runtime().session_manager.set_skill_state(session_id, skill_key, state)
    return {"status": "ok", "document": updated, "state": state}


@app.get("/v1/sessions/{session_id}/kyc/{skill_key}/draft")
async def get_kyc_draft(session_id: str, skill_key: str, request: Request):
    _require_session_access(session_id, _principal(request))
    card = _kyc_card(skill_key)
    state = runtime().session_manager.get_skill_state(session_id, skill_key) or {}
    return {"session_id": session_id, "skill_key": skill_key, "state": state, "completion": _kyc_draft_completion(card, state)}


@app.get("/v1/sessions/{session_id}/kyc/{skill_key}/draft/export")
async def export_kyc_draft(session_id: str, skill_key: str, request: Request):
    _require_session_access(session_id, _principal(request))
    _kyc_card(skill_key)
    state = runtime().session_manager.get_skill_state(session_id, skill_key) or {}
    try:
        path = runtime().kyc_drafts.export_draft(session_id=session_id, skill_key=skill_key, state=state)
    except KycDraftError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return FileResponse(path, media_type="application/json", filename=path.name)


def _review_snapshot(state: dict[str, Any]) -> dict[str, Any] | None:
    """提取确认卡所需的安全 UI 状态，不包含任何执行结果行。"""
    # 普通只读查询没有人工确认步骤，因此完成态、失败态和执行中的
    # 非待确认状态都不应生成 review snapshot。
    if state.get("status") not in PENDING_REVIEW_STATUSES:
        return None
    if not (
        state.get("analysis_plan_review_card")
        or state.get("method_review_card")
        or state.get("method_set_review_card")
        or state.get("method_draft")
        or state.get("method_drafts")
    ):
        return None
    keys = (
        "request_id",
        "review_id",
        "status",
        "analysis_plan",
        "analysis_plan_review_card",
        "method_draft",
        "method_drafts",
        "method_review_card",
        "method_review_cards",
        "method_set_review_card",
        "sql",
    )
    return {key: state.get(key) for key in keys if state.get(key) is not None}


def _sync_pending_review(state: dict[str, Any]) -> None:
    """同步内存中的可确认状态与 session 中用于界面恢复的安全卡片。"""
    request_id = state.get("request_id", "")
    session_id = state.get("session_id", "")
    is_pending = state.get("status") in PENDING_REVIEW_STATUSES and bool(request_id)

    if request_id and session_id:
        runtime().run_store.save(state, _persistable_pending_state(state))

    if session_id:
        runtime().session_manager.set_run_detail(session_id, _safe_run_detail(state))
        review = _review_snapshot(state)
        if request_id and is_pending and review:
            runtime().session_manager.set_review_snapshot(session_id, request_id, review)
        elif request_id:
            # 普通只读查询完成后不再保留可恢复的 review 卡片。
            runtime().session_manager.clear_review_snapshot(session_id, request_id)

    if is_pending:
        PENDING_RUNS[request_id] = dict(state)
        if session_id:
            PENDING_RUNS[session_id] = dict(state)
            runtime().session_manager.set_pending_run_state(
                session_id,
                _persistable_pending_state(state),
            )
            runtime().session_manager.set_pending_review(
                session_id,
                _response_from_state(state).model_dump(mode="json"),
            )
        return

    if request_id:
        PENDING_RUNS.pop(request_id, None)
    if session_id:
        PENDING_RUNS.pop(session_id, None)
        runtime().session_manager.set_pending_run_state(session_id, None)
        runtime().session_manager.set_pending_review(session_id, None)


def _persistable_pending_state(state: dict[str, Any]) -> dict[str, Any]:
    """保存待确认所需状态，排除执行结果和私有分析内容。"""
    excluded = {
        "result", "rows", "referenced_result_data", "execution_result_card",
        "execution_result_cards", "result_narration", "result_narrations",
        "private_analysis", "public_memory_entry", "public_memory_entries",
    }
    return {
        key: value
        for key, value in state.items()
        if key not in excluded
    }


def _load_pending_run(request_id: str, principal: Principal) -> dict[str, Any] | None:
    """按 owner 恢复 run；内存缓存只作为兼容旧状态的加速层。"""
    state = runtime().run_store.get(
        request_id,
        user_id=principal.user_id,
        workspace_id=principal.workspace_id,
    )
    if state is not None:
        PENDING_RUNS[request_id] = dict(state)
        if state.get("session_id"):
            PENDING_RUNS[state["session_id"]] = dict(state)
        return state

    state = PENDING_RUNS.get(request_id)
    if state is not None:
        if (
            str(state.get("user_id") or "local") == principal.user_id
            and str(state.get("workspace_id") or "local") == principal.workspace_id
        ):
            return state
        return None
    manager = runtime().session_manager
    for session in manager.list_sessions(
        user_id=principal.user_id,
        workspace_id=principal.workspace_id,
    ):
        candidate = manager.get_pending_run_state(session["session_id"])
        if candidate and candidate.get("request_id") == request_id:
            if (
                str(candidate.get("user_id") or "local") != principal.user_id
                or str(candidate.get("workspace_id") or "local") != principal.workspace_id
            ):
                continue
            PENDING_RUNS[request_id] = dict(candidate)
            if candidate.get("session_id"):
                PENDING_RUNS[candidate["session_id"]] = dict(candidate)
            return candidate
    return None


def _safe_run_detail(state: dict[str, Any]) -> dict[str, Any]:
    """构建可在右侧面板恢复的运行追踪，严格排除结果数据与 result_ref。"""
    entries: list[dict[str, Any]] = []
    for label, key in (
        ("响应规划", "response_plan"),
        ("安全校验", "action_validation"),
        ("方法草稿", "method_draft"),
        ("SQL", "sql"),
    ):
        value = state.get(key)
        if value:
            entries.append({"label": label, "content": value})
    if state.get("errors"):
        entries.append({"label": "错误", "content": state["errors"], "type": "error"})
    executions = state.get("execution_result_cards") or (
        [state.get("execution_result_card")] if state.get("execution_result_card") else []
    )
    if executions:
        entries.append(
            {
                "label": "执行完成" if len(executions) == 1 else f"执行完成（{len(executions)} 个步骤）",
                "content": (
                    {
                        "row_count": executions[0].get("row_count"),
                        "execution_mode": executions[0].get("execution_mode"),
                        "real_database_used": executions[0].get("real_database_used", False),
                    }
                    if len(executions) == 1
                    else [
                        {
                            "step": index + 1,
                            "row_count": execution.get("row_count"),
                            "execution_mode": execution.get("execution_mode"),
                            "real_database_used": execution.get("real_database_used", False),
                        }
                        for index, execution in enumerate(executions)
                    ]
                ),
                "type": "success" if state.get("status") == "executed_simulated_real" else "error",
            }
        )

    status = state.get("status", "")
    status_text = {
        "analysis_plan_review_ready": "等待确认分析计划",
        "method_review_ready": "等待确认执行方法",
        "prior_result_authorization_pending": "等待授权使用先前结果",
        "executed_simulated_real": "分析已完成",
        "method_execution_failed": "执行失败",
    }.get(status, "已完成")
    status_type = "error" if status == "method_execution_failed" else ("success" if status == "executed_simulated_real" else "")
    skill_detail = state.get("selected_skill_detail") or {}
    return {
        "request_id": state.get("request_id"),
        "status": status,
        "status_text": status_text,
        "status_type": status_type,
        "entries": entries,
        "observability": state.get("observability"),
        "skill_id": skill_detail.get("skill_id"),
        "skill_detail": skill_detail or None,
        "skill_card": state.get("skill_card"),
    }


def _hydrate_current_skill_run_detail(detail: dict[str, Any] | None) -> dict[str, Any] | None:
    """恢复历史 Skill 卡片时使用当前注册表定义，保留会话运行状态。"""
    # Query runs also retain selected_skill_detail for Debug metadata, but
    # that does not mean a query input card was shown. Only rehydrate a card
    # when the run detail explicitly captured one (typically skill_card_ready).
    if not isinstance(detail, dict) or not detail.get("skill_id") or not detail.get("skill_card"):
        return detail
    skill = runtime().skill_registry.resolve(str(detail["skill_id"]))
    if skill is None or not skill.card:
        return detail
    return {
        **detail,
        "skill_id": skill.name,
        "skill_detail": skill.detail_spec(),
        "skill_card": skill.card,
    }


def _response_from_state(state: dict[str, Any]) -> RunResponse:
    # review_id and review cards are UI controls, not generic query metadata.
    # Expose them only while the run is genuinely waiting for confirmation.
    review_pending = state.get("status") in PENDING_REVIEW_STATUSES
    return RunResponse(
        request_id=state.get("request_id", ""),
        session_id=state.get("session_id"),
        review_id=state.get("review_id") if review_pending else None,
        status=state.get("status", "unknown"),
        answer=state.get("answer"),
        errors=state.get("errors", []),
        result_ref=state.get("result_ref"),
        plan_result_ref=state.get("plan_result_ref"),
        result_refs=state.get("result_refs"),
        referenced_result_ref=state.get("referenced_result_ref"),
        public_memory_entry=state.get("public_memory_entry"),
        public_memory_context=state.get("public_memory_context"),
        response_plan=state.get("response_plan"),
        query_request=state.get("query_request"),
        action_validation=state.get("action_validation"),
        selected_skill_detail=state.get("selected_skill_detail"),
        skill_card=state.get("skill_card"),
        schema_candidates=state.get("schema_candidates"),
        selected_schema_tables=state.get("selected_schema_tables"),
        metadata_disclosure=state.get("metadata_disclosure"),
        tool_decision=state.get("tool_decision"),
        planner_used=state.get("planner_used"),
        sql=state.get("sql"),
        row_count=state.get("row_count"),
        analysis_plan=state.get("analysis_plan"),
        analysis_plan_review_card=state.get("analysis_plan_review_card") if review_pending else None,
        method_draft=state.get("method_draft"),
        method_drafts=state.get("method_drafts"),
        harness_review=state.get("harness_review"),
        harness_reviews=state.get("harness_reviews"),
        mock_result=state.get("mock_result"),
        mock_results=state.get("mock_results"),
        internal_method_review=state.get("internal_method_review"),
        validation_report=state.get("validation_report"),
        method_review_card=state.get("method_review_card") if review_pending else None,
        method_review_cards=state.get("method_review_cards") if review_pending else None,
        method_set_review_card=state.get("method_set_review_card") if review_pending else None,
        data_authorization_card=state.get("data_authorization_card") if review_pending else None,
        prior_result_authorization_card=state.get("prior_result_authorization_card") if review_pending else None,
        execution_result_card=state.get("execution_result_card"),
        execution_result_cards=state.get("execution_result_cards"),
        result_narration=state.get("result_narration"),
        result_narrations=state.get("result_narrations"),
        audit=state.get("audit"),
        observability=state.get("observability"),
    )
