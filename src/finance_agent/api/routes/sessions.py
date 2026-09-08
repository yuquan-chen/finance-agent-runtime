from __future__ import annotations

from typing import Any
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, Request

from finance_agent.api.schemas import (
    SessionCreateRequest,
    SessionResponse,
    SkillAgentMessageRequest,
    SkillSessionOpenRequest,
    SkillStateRequest,
)
from finance_agent.kyc.local_drafts import KycDraftError
from finance_agent.security.principal import Principal
from finance_agent.session.thread_store import RESUMABLE_STATUSES
from finance_agent.skills.agent import SkillAgentError

router = APIRouter()


def _app():
    """Resolve app-owned runtime helpers only after the router is imported."""
    from finance_agent.api import app as app_module

    return app_module


def _principal(request: Request) -> Principal:
    return _app()._principal(request)


def _session(session_id: str, principal: Principal) -> dict[str, Any]:
    return _app()._require_session_access(session_id, principal)


def _session_response(session: dict[str, Any]) -> SessionResponse:
    return SessionResponse(
        session_id=session["session_id"],
        title=session["title"],
        created_at=session["created_at"],
        updated_at=session["updated_at"],
        pinned=bool(session.get("metadata", {}).get("pinned", False)),
        message_count=len(session.get("conversation_history", [])),
    )


@router.get("/v1/sessions", response_model=list[SessionResponse])
async def list_sessions(request: Request):
    """列出当前用户和 workspace 的 session。"""
    principal = _principal(request)
    return _app().runtime().session_manager.list_sessions(
        user_id=principal.user_id,
        workspace_id=principal.workspace_id,
    )


@router.post("/v1/sessions", response_model=SessionResponse)
async def create_session(http_request: Request, request: SessionCreateRequest | None = None):
    """创建新的 session。"""
    principal = _principal(http_request)
    title = request.title if request else None
    session = _app().runtime().session_manager.create_session(
        title,
        user_id=principal.user_id,
        workspace_id=principal.workspace_id,
    )
    return _session_response(session)


@router.get("/v1/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, request: Request):
    """获取 session 详情。"""
    return _session_response(_session(session_id, _principal(request)))


@router.delete("/v1/sessions/{session_id}")
async def delete_session(session_id: str, request: Request):
    """删除 session 及其会话级记忆、私有结果和内存检查点。"""
    mod = _app()
    _session(session_id, _principal(request))
    deleted = await mod.runtime().delete_session(session_id)
    if deleted is None:
        raise HTTPException(status_code=404, detail="Session not found")
    for key, state in list(mod.PENDING_RUNS.items()):
        if key == session_id or state.get("session_id") == session_id:
            mod.PENDING_RUNS.pop(key, None)
    return {"status": "ok", "message": "Session deleted", "deleted": deleted}


@router.post("/v1/sessions/{session_id}/pin", response_model=SessionResponse)
async def set_session_pinned(session_id: str, request: Request, pinned: bool = True):
    """置顶或取消置顶某个会话。"""
    mod = _app()
    _session(session_id, _principal(request))
    session = mod.runtime().session_manager.set_session_pinned(session_id, pinned)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return _session_response(session)


@router.get("/v1/sessions/{session_id}/history")
async def get_session_history(session_id: str, request: Request, limit: int | None = None):
    """获取 session 的对话历史。"""
    mod = _app()
    principal = _principal(request)
    _session(session_id, principal)
    manager = mod.runtime().session_manager
    history = manager.get_conversation_history(session_id, limit)
    pending_review = manager.get_pending_review(session_id)
    persisted_state = manager.get_pending_run_state(session_id)
    if persisted_state and persisted_state.get("request_id"):
        mod.PENDING_RUNS[persisted_state["request_id"]] = dict(persisted_state)
        mod.PENDING_RUNS[session_id] = dict(persisted_state)
        # 已完成/失败的运行也要经过同步，以清理升级前遗留的待确认状态。
        mod._sync_pending_review(persisted_state)
        pending_review = manager.get_pending_review(session_id)
    if pending_review is not None and pending_review.get("status") not in mod.PENDING_REVIEW_STATUSES:
        manager.clear_review_snapshot(session_id, str(pending_review.get("request_id") or ""))
        manager.set_pending_review(session_id, None)
        pending_review = None
    if pending_review is None:
        in_memory_state = mod.PENDING_RUNS.get(session_id)
        if in_memory_state and in_memory_state.get("status") in mod.PENDING_REVIEW_STATUSES:
            mod._sync_pending_review(in_memory_state)
            pending_review = manager.get_pending_review(session_id)

    # A review snapshot is restorable only when it is backed by the same
    # currently pending run.  Older versions could leave a card in the
    # timeline after the run had already failed or completed; never revive
    # those cards on refresh.
    pending_state = None
    if persisted_state and persisted_state.get("status") in mod.PENDING_REVIEW_STATUSES:
        pending_state = persisted_state
    elif not persisted_state:
        in_memory_state = mod.PENDING_RUNS.get(session_id)
        if in_memory_state and in_memory_state.get("status") in mod.PENDING_REVIEW_STATUSES:
            pending_state = in_memory_state
    pending_request_id = str((pending_state or {}).get("request_id") or "")
    review_request_id = str((pending_review or {}).get("request_id") or "")
    if pending_request_id and pending_review and review_request_id == pending_request_id:
        manager.clear_review_snapshots(session_id, keep_request_id=pending_request_id)
    elif pending_review or manager.get_timeline(session_id):
        manager.clear_review_snapshots(session_id)
        manager.set_pending_review(session_id, None)
        pending_review = None

    kyc_state = manager.get_skill_state(session_id, "kyc_intake") or {}
    side_attachment_ids: set[str] = set()
    for side_summary in manager.list_skill_sessions(session_id):
        side_session = manager.get_skill_session(
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
    kyc_card = mod.runtime().skill_registry.get("kyc_intake")
    attachment_upload_options = [
        {"id": item.get("id"), "label": item.get("label") or item.get("id")}
        for item in ((kyc_card.card if kyc_card else {}) or {}).get("uploads", [])
        if item.get("id")
    ]
    return {
        "session_id": session_id,
        "history": history,
        "timeline": manager.get_timeline(session_id),
        "private_analysis": manager.get_private_analysis(session_id),
        "pending_review": pending_review,
        "attachment_reviews": pending_attachment_reviews,
        "attachment_upload_options": attachment_upload_options,
        "run_detail": mod._hydrate_current_skill_run_detail(manager.get_run_detail(session_id)),
    }


@router.get("/v1/sessions/{session_id}/skill-state/{skill_key}")
async def get_skill_state(session_id: str, skill_key: str, request: Request):
    """读取当前会话中某个 Skill 的表单/草稿状态。"""
    mod = _app()
    _session(session_id, _principal(request))
    return {
        "session_id": session_id,
        "skill_key": skill_key,
        "state": mod.runtime().session_manager.get_skill_state(session_id, skill_key) or {},
    }


@router.put("/v1/sessions/{session_id}/skill-state/{skill_key}")
async def put_skill_state(
    session_id: str,
    skill_key: str,
    request: SkillStateRequest,
    http_request: Request,
):
    """保存当前会话中某个 Skill 的表单/草稿状态。"""
    mod = _app()
    _session(session_id, _principal(http_request))
    existing = mod.runtime().session_manager.get_skill_state(session_id, skill_key) or {}
    merged_state = {**existing, **request.state}
    saved = mod.runtime().session_manager.set_skill_state(session_id, skill_key, merged_state)
    if saved is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "ok", "session_id": session_id, "skill_key": skill_key, "state": merged_state}


@router.get("/v1/sessions/{session_id}/skill-sessions")
async def list_skill_sessions(session_id: str, request: Request):
    """列出当前主会话下可恢复的侧边 Skill Agent。"""
    mod = _app()
    _session(session_id, _principal(request))
    return {
        "session_id": session_id,
        "skill_sessions": mod.runtime().session_manager.list_skill_sessions(session_id),
    }


@router.post("/v1/sessions/{session_id}/skill-sessions")
async def open_skill_session(
    session_id: str,
    request: SkillSessionOpenRequest,
    http_request: Request,
):
    """打开或恢复通用侧边 Skill Agent。"""
    mod = _app()
    _session(session_id, _principal(http_request))
    skill_id = mod._canonical_skill_id(request.skill_id)
    try:
        return mod.runtime().open_skill_agent(session_id, skill_id or request.skill_id)
    except SkillAgentError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/v1/skill-sessions/{skill_session_id}")
async def get_skill_session(skill_session_id: str, request: Request):
    """读取侧边 Agent 的独立消息、卡片和共享状态。"""
    mod = _app()
    mod._require_skill_session_access(skill_session_id, _principal(request))
    try:
        return mod.runtime().get_skill_agent(skill_session_id)
    except SkillAgentError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/v1/skill-sessions/{skill_session_id}/messages")
async def send_skill_session_message(
    skill_session_id: str,
    request: SkillAgentMessageRequest,
    http_request: Request,
):
    """向侧边 Agent 发消息；不会触发主聊天的财务查询链路。"""
    mod = _app()
    mod._require_skill_session_access(skill_session_id, _principal(http_request))
    try:
        return mod.runtime().send_skill_agent_message(
            skill_session_id, request.message, request.attachment_ids
        )
    except SkillAgentError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail="Skill Agent 暂时无法处理这条消息") from error


@router.post("/v1/skill-sessions/{skill_session_id}/attachments")
async def upload_skill_session_attachment(skill_session_id: str, request: Request):
    """Upload a side Agent attachment into the parent session inbox and OCR it."""
    mod = _app()
    skill_session = mod._require_skill_session_access(skill_session_id, _principal(request))
    if skill_session.get("status") not in RESUMABLE_STATUSES:
        raise HTTPException(status_code=400, detail="skill session is not resumable")
    parent_id = skill_session["parent_session_id"]
    if mod.runtime().session_manager.get_session(parent_id) is None:
        raise HTTPException(status_code=404, detail="parent session not found")
    content_length = request.headers.get("content-length")
    max_size_mb = 10
    if content_length and content_length.isdigit() and int(content_length) > max_size_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"文件不能超过 {max_size_mb} MB")
    try:
        document = mod.runtime().kyc_drafts.save_inbox_upload(
            session_id=parent_id,
            filename=unquote(request.headers.get("x-file-name", "")),
            content_type=request.headers.get("content-type", ""),
            content=await request.body(),
            max_size_mb=max_size_mb,
        )
        if document.get("ocr_status") == "pending":
            try:
                document = mod.runtime().kyc_drafts.run_ocr(
                    session_id=parent_id, skill_key="chat_inbox", record=document
                )
            except KycDraftError as error:
                document = {**document, "ocr_status": "failed", "ocr_message": str(error)}
    except KycDraftError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    mod.runtime().session_manager.add_attachment(parent_id, document)
    return {"status": "ok", "attachment": document}


@router.post("/v1/skill-sessions/{skill_session_id}/close")
async def close_skill_session(skill_session_id: str, request: Request):
    """关闭侧边 Agent；共享草稿保留，之后可以重新打开。"""
    mod = _app()
    mod._require_skill_session_access(skill_session_id, _principal(request))
    updated = mod.runtime().session_manager.update_skill_session(
        skill_session_id, {"status": "closed"}
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="skill session not found")
    return {"status": "ok", "skill_session": updated}
