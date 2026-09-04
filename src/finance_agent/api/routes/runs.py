from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from finance_agent.api.schemas import MethodReviewRevisionRequest, RunRequest, RunResponse
from finance_agent.security.principal import Principal

router = APIRouter()


def _app():
    # Import lazily so the route group can be included by app.py without a
    # module cycle. The runtime and compatibility cache live in app.py.
    from finance_agent.api import app as app_module

    return app_module


def _principal(request: Request) -> Principal:
    return _app()._principal(request)


def _response(state: dict[str, Any]) -> RunResponse:
    return _app()._response_from_state(state)


def _pending(request_id: str, principal: Principal) -> dict[str, Any] | None:
    return _app()._load_pending_run(request_id, principal)


def _claim(request_id: str, action: str, state: dict[str, Any], principal: Principal, request: Request, instruction: str | None = None):
    mod = _app()
    return mod._claim_action(
        request_id,
        action=action,
        state=state,
        principal=principal,
        request=request,
        instruction=instruction,
    )


@router.post("/v1/runs", response_model=RunResponse)
async def create_run(request: RunRequest, http_request: Request) -> RunResponse:
    mod = _app()
    principal = _principal(http_request)
    if request.session_id:
        mod._require_session_access(request.session_id, principal)
    skill_id = mod._canonical_skill_id(request.skill_id)
    try:
        state = await mod.runtime().invoke(
            request.question,
            session_id=request.session_id,
            requested_skill_id=skill_id,
            user_id=principal.user_id,
            workspace_id=principal.workspace_id,
        )
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    mod._sync_pending_review(state)
    return _response(state)


@router.get("/v1/runs/stream")
async def create_run_stream(
    request: Request,
    question: str,
    session_id: str | None = None,
    skill_id: str | None = None,
):
    mod = _app()
    principal = _principal(request)
    if session_id:
        mod._require_session_access(session_id, principal)
    skill_id = mod._canonical_skill_id(skill_id)

    async def event_generator():
        try:
            yield f"data: {json.dumps({'type': 'start', 'message': '开始处理请求...'})}\n\n"
            final_state = None
            emitted_errors: tuple[str, ...] = ()
            emitted_values: set[str] = set()
            event_keys = {
                "plan_response": "response_plan",
                "validate_action": "action_validation",
                "generate_method": "method_draft",
                "repair_method": "method_draft",
                "skill_agent": "response_plan",
            }
            async for stage, state in mod.runtime().astream(
                question,
                session_id=session_id,
                requested_skill_id=skill_id,
                user_id=principal.user_id,
                workspace_id=principal.workspace_id,
            ):
                if stage == "complete":
                    final_state = state
                    break
                event_key = event_keys.get(stage)
                if event_key and state.get(event_key) and event_key not in emitted_values:
                    emitted_values.add(event_key)
                    yield f"data: {json.dumps({'type': event_key, 'data': state[event_key]})}\n\n"
                if stage in {"render_direct_response", "render_method_card", "refuse_method", "audit"} and state.get("sql") and "sql" not in emitted_values:
                    emitted_values.add("sql")
                    yield f"data: {json.dumps({'type': 'sql', 'data': state['sql']})}\n\n"
                errors = tuple(state.get("errors") or [])
                if errors and errors != emitted_errors:
                    emitted_errors = errors
                    yield f"data: {json.dumps({'type': 'errors', 'data': list(errors)})}\n\n"
                # 通用阶段事件用于调试面板，保持原有事件类型兼容。
                yield f"data: {json.dumps({'type': 'stage', 'stage': stage, 'status': state.get('status')})}\n\n"
            if final_state is None:
                raise RuntimeError("stream ended before completion")
            state = final_state
            mod._sync_pending_review(state)
            yield f"data: {json.dumps({'type': 'complete', 'data': _response(state).model_dump()})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.get("/v1/runs/{request_id}", response_model=RunResponse)
async def get_run(request_id: str, request: Request) -> RunResponse:
    state = _pending(request_id, _principal(request))
    if state is None:
        raise HTTPException(status_code=404, detail="run not found")
    return _response(state)


@router.post("/v1/runs/{request_id}/analysis-plan/approve", response_model=RunResponse)
async def approve_analysis_plan(request_id: str, request: Request) -> RunResponse:
    mod = _app()
    principal = _principal(request)
    state = _pending(request_id, principal)
    if state is None:
        raise HTTPException(status_code=404, detail="pending analysis plan review not found")
    action = "analysis_plan_approve"
    try:
        _, key = _claim(request_id, action, state, principal, request)
    except mod._CompletedAction as completed:
        return RunResponse.model_validate(completed.payload)
    prior_review_id = state.get("review_id")
    try:
        state = await mod.runtime().approve_analysis_plan(state)
    except ValueError as exc:
        mod.runtime().run_store.fail_action(request_id, action=action, idempotency_key=key)
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session_id = state.get("session_id")
    if session_id:
        mod.runtime().session_manager.set_review_status(session_id, request_id, "analysis_plan_approved", review_id=prior_review_id)
        if state.get("answer"):
            mod.runtime().session_manager.add_message(session_id, "assistant", state["answer"], request_id=request_id)
    result = _response(state)
    mod.runtime().run_store.complete_action(
        request_id, action=action, idempotency_key=key,
        state=mod._persistable_pending_state(state), payload=mod._safe_action_response(state),
    )
    mod._sync_pending_review(state)
    return result


@router.post("/v1/runs/{request_id}/method-review/approve", response_model=RunResponse)
async def approve_method_review(request_id: str, request: Request) -> RunResponse:
    mod = _app()
    principal = _principal(request)
    state = _pending(request_id, principal)
    if state is None:
        raise HTTPException(status_code=404, detail="pending method review not found")
    action = "method_review_approve"
    try:
        _, key = _claim(request_id, action, state, principal, request)
    except mod._CompletedAction as completed:
        return RunResponse.model_validate(completed.payload)
    review_id = state.get("review_id")
    try:
        state = await mod.runtime().approve_method_review(state)
    except ValueError as exc:
        mod.runtime().run_store.fail_action(request_id, action=action, idempotency_key=key)
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if state.get("session_id"):
        mod.runtime().session_manager.set_review_status(
            state["session_id"], request_id, state.get("status", "executed_simulated_real"), review_id=review_id
        )
    result = _response(state)
    mod.runtime().run_store.complete_action(
        request_id, action=action, idempotency_key=key,
        state=mod._persistable_pending_state(state), payload=mod._safe_action_response(state),
    )
    mod._sync_pending_review(state)
    return result


@router.post("/v1/runs/{request_id}/method-review/revise", response_model=RunResponse)
async def revise_method_review(
    request_id: str, revision: MethodReviewRevisionRequest, request: Request
) -> RunResponse:
    mod = _app()
    principal = _principal(request)
    state = _pending(request_id, principal)
    if state is None:
        raise HTTPException(status_code=404, detail="pending method review not found")
    action = "method_review_revise"
    try:
        _, key = _claim(request_id, action, state, principal, request, revision.instruction)
    except mod._CompletedAction as completed:
        return RunResponse.model_validate(completed.payload)
    prior_review_id = state.get("review_id")
    try:
        state = await mod.runtime().revise_method_review(state, revision.instruction)
    except ValueError as exc:
        mod.runtime().run_store.fail_action(request_id, action=action, idempotency_key=key)
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session_id = state.get("session_id")
    if session_id:
        mod.runtime().session_manager.set_review_status(session_id, request_id, "method_review_revised", review_id=prior_review_id)
        mod.runtime().session_manager.add_message(session_id, "user", revision.instruction, request_id=request_id)
        if state.get("answer"):
            mod.runtime().session_manager.add_message(session_id, "assistant", state["answer"], request_id=request_id)
    result = _response(state)
    mod.runtime().run_store.complete_action(
        request_id, action=action, idempotency_key=key,
        state=mod._persistable_pending_state(state), payload=mod._safe_action_response(state),
    )
    mod._sync_pending_review(state)
    return result


async def _approve_authorization(request_id: str, request: Request, action: str, method) -> RunResponse:
    mod = _app()
    principal = _principal(request)
    state = _pending(request_id, principal)
    if state is None:
        raise HTTPException(status_code=404, detail="pending run not found")
    try:
        _, key = _claim(request_id, action, state, principal, request)
    except mod._CompletedAction as completed:
        return RunResponse.model_validate(completed.payload)
    try:
        state = await method(state)
    except ValueError as exc:
        mod.runtime().run_store.fail_action(request_id, action=action, idempotency_key=key)
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        mod.runtime().run_store.fail_action(request_id, action=action, idempotency_key=key)
        raise HTTPException(status_code=500, detail={"errors": [str(exc)]}) from exc
    result = _response(state)
    mod.runtime().run_store.complete_action(
        request_id, action=action, idempotency_key=key,
        state=mod._persistable_pending_state(state), payload=mod._safe_action_response(state),
    )
    mod._sync_pending_review(state)
    return result


@router.post("/v1/runs/{request_id}/data-authorization/approve", response_model=RunResponse)
async def approve_data_authorization(request_id: str, request: Request) -> RunResponse:
    mod = _app()
    return await _approve_authorization(request_id, request, "data_authorization_approve", mod.runtime().approve_data_authorization)


@router.post("/v1/runs/{request_id}/prior-result-authorization/approve", response_model=RunResponse)
async def approve_prior_result_authorization(request_id: str, request: Request) -> RunResponse:
    mod = _app()
    return await _approve_authorization(request_id, request, "prior_result_authorization_approve", mod.runtime().approve_prior_result_authorization)
