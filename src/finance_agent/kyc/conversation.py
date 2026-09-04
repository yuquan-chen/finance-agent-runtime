from __future__ import annotations

import json
from typing import Any

from finance_agent.llm.provider import LlmProvider


def _section_context(card: dict[str, Any], fields: dict[str, Any]) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    definitions = {item.get("id"): item for item in card.get("fields", []) if item.get("id")}
    for section in card.get("sections", []):
        visible = [definitions[field_id] for field_id in section.get("fields", []) if field_id in definitions]
        missing = [item for item in visible if item.get("required") and not fields.get(item.get("id"))]
        if missing:
            return section, visible
    return None, []


def _field_for_prompt(field: dict[str, Any]) -> dict[str, Any]:
    result = {
        "id": field.get("id"),
        "label": field.get("label"),
        "type": field.get("type", "text"),
        "required": bool(field.get("required")),
    }
    if field.get("options"):
        result["options"] = field["options"]
    return result


def update_from_conversation(
    *,
    message: str,
    card: dict[str, Any],
    state: dict[str, Any],
    provider: LlmProvider,
) -> dict[str, Any]:
    """Extract explicit field values using the configured field contract.

    The model may only propose fields in the current progressive section. The
    returned patch is validated again here before it is persisted.
    """
    current_fields = dict(state.get("fields") or {})
    section, visible_fields = _section_context(card, current_fields)
    if section is None:
        return {
            "updates": {},
            "uncertain": [],
            "message": "当前卡片中的必填字段已经填写完成，可以点击保存草稿并进行检查。",
        }

    prompt = {
        "message": message,
        "current_section": {
            "id": section.get("id"),
            "title": section.get("title"),
            "fields": [_field_for_prompt(field) for field in visible_fields],
        },
        "already_filled": {
            field.get("id"): current_fields[field.get("id")]
            for field in visible_fields
            if field.get("id") in current_fields and current_fields[field.get("id")] not in ("", None, False)
        },
    }
    messages = [
        {
            "role": "system",
            "content": (
                "你是 KYC 表单填写助手。只从用户本条消息中提取明确表达的值。"
                "只能使用 current_section.fields 中的字段 id，不得猜测、补全或编造值。"
                "如果一个表达可能对应多个字段，放入 uncertain，不要写入 updates。"
                "只返回 JSON：{\"updates\":{\"field_id\":\"value\"},"
                "\"uncertain\":[{\"field_id\":\"...\",\"reason\":\"...\"}]}。"
                "checkbox 只返回 true 或 false；select 只能返回 options 中的 value。"
            ),
        },
        {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
    ]
    parsed, _ = provider.chat_json(messages, temperature=0, max_tokens=800)
    proposed = parsed.get("updates") if isinstance(parsed, dict) else {}
    proposed = proposed if isinstance(proposed, dict) else {}
    definitions = {field.get("id"): field for field in visible_fields}
    updates: dict[str, Any] = {}
    for field_id, value in proposed.items():
        field = definitions.get(field_id)
        if field is None or value is None:
            continue
        if field.get("type") == "checkbox":
            if isinstance(value, bool):
                updates[field_id] = value
            continue
        if not isinstance(value, (str, int, float)):
            continue
        normalized = str(value).strip()
        if not normalized:
            continue
        if field.get("type") == "select":
            options = {
                option if isinstance(option, str) else option.get("value")
                for option in field.get("options", [])
            }
            if normalized not in options:
                continue
        updates[field_id] = normalized

    next_fields = {**current_fields, **updates}
    _, next_visible = _section_context(card, next_fields)
    missing_labels = [
        field.get("label") or field.get("id")
        for field in next_visible
        if field.get("required") and not next_fields.get(field.get("id"))
    ]
    if updates:
        message_text = "已记录：" + "、".join(
            definitions[field_id].get("label") or field_id for field_id in updates
        )
        if missing_labels:
            message_text += "。还需要填写：" + "、".join(missing_labels)
        else:
            message_text += "。可以继续描述下一组信息。"
    else:
        message_text = "我没有从这句话中识别到当前阶段的明确字段值，请按卡片字段继续描述。"
    uncertain = parsed.get("uncertain", []) if isinstance(parsed, dict) else []
    return {
        "updates": updates,
        "uncertain": uncertain if isinstance(uncertain, list) else [],
        "message": message_text,
    }
