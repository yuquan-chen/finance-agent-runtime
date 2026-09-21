"""Runtime metrics and optional LangSmith reporting.

Local metrics are always collected. LangSmith is opt-in and receives only
stage names, timings, token counts, and opaque run identifiers.
"""
from __future__ import annotations

import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

_CURRENT_SPAN: ContextVar[tuple[dict[str, Any], dict[str, Any]] | None] = ContextVar(
    "finance_agent_current_span", default=None
)


def new_observability(trace_id: str) -> dict[str, Any]:
    return {
        "trace_id": trace_id,
        "started_at": time.time(),
        "finished_at": None,
        "total_elapsed_ms": None,
        "spans": [],
        "llm_calls": [],
        "token_usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        "langsmith": {"status": "disabled"},
    }


@contextmanager
def observe_span(observability: dict[str, Any], name: str, *, kind: str = "module") -> Iterator[None]:
    span = {
        "name": name,
        "kind": kind,
        "started_at": time.time(),
        "finished_at": None,
        "duration_ms": None,
        "status": "running",
        "token_usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
    }
    observability.setdefault("spans", []).append(span)
    token = _CURRENT_SPAN.set((observability, span))
    try:
        yield
    except Exception as exc:
        span["status"] = "error"
        span["error_type"] = type(exc).__name__
        raise
    finally:
        finished_at = time.time()
        span["finished_at"] = finished_at
        span["duration_ms"] = max(0, int((finished_at - span["started_at"]) * 1000))
        if span["status"] == "running":
            span["status"] = "completed"
        _CURRENT_SPAN.reset(token)


def record_llm_response(response: Any, *, operation: str | None = None) -> None:
    current = _CURRENT_SPAN.get()
    if current is None:
        return
    observability, span = current
    usage = getattr(response, "token_usage", None) or {}
    normalized = {
        "input_tokens": int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or usage.get("completion_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
    }
    if not normalized["total_tokens"]:
        normalized["total_tokens"] = normalized["input_tokens"] + normalized["output_tokens"]
    span_usage = span.setdefault("token_usage", {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0})
    for key, value in normalized.items():
        span_usage[key] = span_usage.get(key, 0) + value
    observability_usage = observability.setdefault(
        "token_usage", {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    )
    for key, value in normalized.items():
        observability_usage[key] = observability_usage.get(key, 0) + value
    observability.setdefault("llm_calls", []).append(
        {
            "operation": operation or span.get("name"),
            "provider": getattr(response, "provider", None),
            "model": getattr(response, "model", None),
            "elapsed_ms": getattr(response, "elapsed_ms", None),
            "token_usage": normalized,
        }
    )


def finalize_observability(observability: dict[str, Any], *, status: str, settings: Any) -> dict[str, Any]:
    finished_at = time.time()
    observability["finished_at"] = finished_at
    observability["total_elapsed_ms"] = max(0, int((finished_at - observability["started_at"]) * 1000))
    observability["status"] = status
    observability["langsmith"] = publish_to_langsmith(observability, settings)
    return observability


def publish_to_langsmith(observability: dict[str, Any], settings: Any) -> dict[str, Any]:
    """Best-effort upload of metadata-only spans to LangSmith."""
    enabled = bool(getattr(settings, "langsmith_tracing", False))
    api_key = os.environ.get("LANGSMITH_API_KEY", "")
    if not enabled or not api_key:
        return {"status": "disabled"}
    try:
        from langsmith import Client, RunTree

        project_name = getattr(settings, "langsmith_project", "dogpay-admin-agent")
        endpoint = getattr(settings, "langsmith_endpoint", "") or None
        client = Client(api_url=endpoint, api_key=api_key)
        root = RunTree(
            name="dogpay_admin_agent_run",
            run_type="chain",
            project_name=project_name,
            ls_client=client,
            inputs={"trace_id": observability.get("trace_id")},
            extra={"metadata": {"source": "finance_agent_runtime"}},
            tags=["dogpay-admin-agent"],
        )
        for span in observability.get("spans", []):
            child = root.create_child(
                name=str(span.get("name") or "module"),
                run_type="llm" if span.get("kind") == "llm" else "chain",
                inputs={"trace_id": observability.get("trace_id")},
                start_time=_timestamp(span.get("started_at")),
                end_time=_timestamp(span.get("finished_at")),
                extra={"metadata": {"duration_ms": span.get("duration_ms"), "token_usage": span.get("token_usage")}},
            )
            child.end(outputs={"duration_ms": span.get("duration_ms")}, error=span.get("error_type"))
        root.end(
            outputs={
                "status": observability.get("status"),
                "total_elapsed_ms": observability.get("total_elapsed_ms"),
                "token_usage": observability.get("token_usage"),
            }
        )
        root.post(exclude_child_runs=False)
        return {"status": "sent", "project": project_name}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error_type": type(exc).__name__}


def _timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(float(value), tz=UTC)
