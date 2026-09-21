from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field

from finance_agent.query.safe_requests import SafeQueryRequest

router = APIRouter()


class SafeQueryResponse(BaseModel):
    request_id: str
    query_id: str
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int
    elapsed_ms: int


def _app():
    from finance_agent.api import app as app_module

    return app_module


@router.post("/v1/internal/query", response_model=SafeQueryResponse)
def execute_safe_query(query: SafeQueryRequest, request: Request) -> SafeQueryResponse:
    """Test-only safe query boundary; callers cannot submit SQL."""
    mod = _app()
    principal = mod._principal(request)
    runtime = mod.runtime()
    executor = runtime.executor
    execute_request = getattr(executor, "execute_safe_request", None)
    if not callable(execute_request):
        raise HTTPException(status_code=503, detail="safe database query executor is not enabled")

    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    try:
        result = execute_request(query, mod.safe_query_registry())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        runtime.audit_logger.append(
            {
                "event_type": "safe_query_failed",
                "request_id": request_id,
                "user_id": principal.user_id,
                "workspace_id": principal.workspace_id,
                "query_id": query.query_id,
                "param_names": sorted(query.params),
                "error_type": type(exc).__name__,
            }
        )
        raise HTTPException(status_code=502, detail="safe query execution failed") from exc

    runtime.audit_logger.append(
        {
            "event_type": "safe_query_executed",
            "request_id": request_id,
            "user_id": principal.user_id,
            "workspace_id": principal.workspace_id,
            "query_id": query.query_id,
            "param_names": sorted(query.params),
            "page": query.page,
            "page_size": query.page_size,
            "row_count": result.row_count,
            "elapsed_ms": result.elapsed_ms,
        }
    )
    return SafeQueryResponse(
        request_id=request_id,
        query_id=query.query_id,
        rows=jsonable_encoder(result.rows),
        row_count=result.row_count,
        elapsed_ms=result.elapsed_ms,
    )
