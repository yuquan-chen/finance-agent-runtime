"""LLM-assisted classification for KYC attachments.

OCR text is treated as evidence only. This module returns validated candidates
for the UI to review; it never mutates the KYC draft.
"""
from __future__ import annotations

import json
from typing import Any

from finance_agent.llm.provider import LlmProvider


def _field_contract(card: dict[str, Any]) -> list[dict[str, Any]]:
    fields = []
    for field in card.get("fields", []):
        if not field.get("id"):
            continue
        item = {
            "id": field["id"],
            "label": field.get("label") or field["id"],
            "type": field.get("type", "text"),
            "required": bool(field.get("required")),
        }
        if field.get("options"):
            item["options"] = field["options"]
        fields.append(item)
    return fields


def _document_contract(card: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"id": item["id"], "label": item.get("label") or item["id"]}
        for item in card.get("uploads", [])
        if item.get("id")
    ]


def _scalar_candidate(field: dict[str, Any], value: Any) -> str | bool | int | float | None:
    if field.get("type") == "checkbox":
        return value if isinstance(value, bool) else None
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    if field.get("type") == "select":
        options = {
            option if isinstance(option, str) else option.get("value")
            for option in field.get("options", [])
        }
        if normalized not in options:
            return None
    return normalized


def _confidence(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def extract_attachment_reviews(
    *,
    card: dict[str, Any],
    attachments: list[dict[str, Any]],
    provider: LlmProvider,
) -> list[dict[str, Any]]:
    """Classify OCR evidence and extract field candidates without merging them."""
    documents = _document_contract(card)
    fields = _field_contract(card)
    document_ids = {item["id"] for item in documents}
    field_by_id = {item["id"]: item for item in fields}
    prompt = {
        "documents": documents,
        "fields": fields,
        "attachments": [
            {
                "attachment_id": item.get("document_id"),
                "filename": item.get("name"),
                "ocr_status": item.get("ocr_status"),
                "ocr_text": str(item.get("ocr_text") or "")[:12000],
            }
            for item in attachments
        ],
    }
    messages = [
        {
            "role": "system",
            "content": (
                "你是 KYC 材料识别助手。只能根据给出的 OCR 原文返回候选结果，不能猜测或补全。"
                "document_type 必须使用 documents 中的 id；无法确定时返回 null。"
                "field_candidates 只能使用 fields 中的 id；只有 OCR 原文明确出现的值才能返回。"
                "每个候选都要带 confidence 和 evidence。只返回 JSON："
                "{\"documents\":[{\"attachment_id\":\"...\",\"document_type\":\"...\"或null,"
                "\"confidence\":0到1,\"field_candidates\":[{\"field_id\":\"...\","
                "\"value\":\"...\",\"confidence\":0到1,\"evidence\":\"...\"}]}]}"
            ),
        },
        {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
    ]
    parsed, _ = provider.chat_json(messages, temperature=0, max_tokens=3000)
    raw_results = parsed.get("documents") if isinstance(parsed, dict) else []
    raw_results = raw_results if isinstance(raw_results, list) else []
    by_attachment = {
        str(item.get("attachment_id")): item
        for item in raw_results
        if isinstance(item, dict) and item.get("attachment_id")
    }

    reviews: list[dict[str, Any]] = []
    for attachment in attachments:
        attachment_id = str(attachment.get("document_id") or "")
        raw = by_attachment.get(attachment_id, {})
        document_type = raw.get("document_type")
        if document_type not in document_ids:
            document_type = None
        candidates = []
        for candidate in raw.get("field_candidates", []) if isinstance(raw, dict) else []:
            if not isinstance(candidate, dict):
                continue
            field = field_by_id.get(candidate.get("field_id"))
            if not field:
                continue
            value = _scalar_candidate(field, candidate.get("value"))
            if value is None:
                continue
            candidates.append(
                {
                    "field_id": field["id"],
                    "label": field["label"],
                    "value": value,
                    "confidence": _confidence(candidate.get("confidence", 0)),
                    "evidence": str(candidate.get("evidence") or "")[:240],
                }
            )
        reviews.append(
            {
                "attachment_id": attachment_id,
                "filename": attachment.get("name") or "材料",
                "ocr_status": attachment.get("ocr_status"),
                "ocr_message": attachment.get("ocr_message"),
                "suggested_upload_id": document_type,
                "confidence": _confidence(raw.get("confidence", 0)) if isinstance(raw, dict) else 0.0,
                "field_candidates": candidates,
                "status": "pending_confirmation",
            }
        )
    return reviews
