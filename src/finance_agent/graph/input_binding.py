"""Backend-only binding of Tool filter semantics to SQL input slots."""
from __future__ import annotations

import re
from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import Any


def merge_filter_specs(
    base_specs: list[dict[str, Any]], current_specs: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Overlay current filter semantics onto a safe historical query."""
    merged: dict[str, dict[str, Any]] = {}
    for spec in [*base_specs, *current_specs]:
        if isinstance(spec, dict) and spec.get("name"):
            merged[str(spec["name"])] = {
                key: value
                for key, value in spec.items()
                if key in {"name", "operator", "value_type"}
            }
    return list(merged.values())


def normalize_relative_filter_values(
    params: dict[str, Any],
    filter_specs: list[dict[str, Any]],
    goal: str,
) -> dict[str, Any]:
    """Keep relative time expressions from the user as the source of truth.

    Models sometimes turn ``今年`` into an absolute range using the wrong
    reference year.  The binder resolves the expression against the runtime
    clock after planning, so preserve the relative phrase whenever the goal
    still contains one instead of trusting the model's guessed dates.
    """
    normalized = dict(params)
    goal_text = " ".join(str(goal or "").split())
    if not goal_text:
        return normalized

    relative_patterns = (
        r"(?:今年|本年|这一年|本年度)(?:的)?(?:上半年|下半年)?",
        r"(?:去年|上一年|上年度)(?:的)?(?:上半年|下半年)?",
        r"(?:本月|这个月|上月|上个月)",
        r"(?:最近|近|过去)\s*(?:\d+|[零一二两三四五六七八九十百]+)\s*(?:天|日|days?|周|weeks?|月|个月|months?|年|years?)",
    )
    match = next(
        (re.search(pattern, goal_text, re.IGNORECASE) for pattern in relative_patterns),
        None,
    )
    if not match:
        return normalized
    relative_value = match.group(0).rstrip("的")
    for spec in filter_specs:
        if not isinstance(spec, dict) or not spec.get("name"):
            continue
        if str(spec.get("value_type") or "") == "date_range":
            source_name = str(spec["name"])
            if source_name in normalized:
                normalized[source_name] = relative_value
    return normalized


def sql_input_slots(
    params: dict[str, Any],
    filter_specs: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    """Create opaque slots with semantic types; values stay backend-only."""
    specs_by_name = {
        str(spec.get("name")): spec
        for spec in (filter_specs or [])
        if isinstance(spec, dict) and spec.get("name")
    }
    slots: list[dict[str, str]] = []
    slot_index = 1
    for source_name, value in sorted(params.items()):
        if value is None:
            continue
        spec = specs_by_name.get(str(source_name), {})
        operator = str(spec.get("operator") or "eq")
        value_type = str(spec.get("value_type") or "")
        if not value_type:
            if operator == "between":
                value_type = "date_range" if isinstance(value, str) else "list"
            elif isinstance(value, bool):
                value_type = "boolean"
            elif isinstance(value, (int, float)):
                value_type = "number"
            elif isinstance(value, list):
                value_type = "list"
            else:
                value_type = "text"
        semantic = str(spec.get("name") or source_name).replace("_", " ")
        if operator == "between" or value_type == "date_range":
            slots.extend(
                [
                    {
                        "id": f"input_{slot_index}_start",
                        "source_param": str(source_name),
                        "bound_part": "start",
                        "type": "date" if value_type == "date_range" else value_type,
                        "semantic": f"{semantic} start",
                        "operator": "gte",
                    },
                    {
                        "id": f"input_{slot_index}_end",
                        "source_param": str(source_name),
                        "bound_part": "end",
                        "type": "date" if value_type == "date_range" else value_type,
                        "semantic": f"{semantic} end",
                        "operator": "lt",
                    },
                ]
            )
            slot_index += 1
            continue
        slots.append(
            {
                "id": f"input_{slot_index}",
                "source_param": str(source_name),
                "type": value_type,
                "semantic": semantic,
                "operator": operator,
            }
        )
        slot_index += 1
    return slots


def planner_input_slots(slots: list[dict[str, str]]) -> list[dict[str, str]]:
    """Expose only safe slot metadata to the SQL-planning model."""
    return [
        {
            "id": slot["id"],
            "type": slot["type"],
            "semantic": slot["semantic"],
            "operator": slot.get("operator", "eq"),
        }
        for slot in slots
    ]


def redact_sql_planning_goal(
    goal: str,
    slots: list[dict[str, str]],
    params: dict[str, Any],
) -> str:
    """Remove known user values before they reach the SQL-planning LLM."""
    redacted = goal
    grouped: dict[str, list[dict[str, str]]] = {}
    for slot in slots:
        grouped.setdefault(slot["source_param"], []).append(slot)
    for source_param, source_slots in grouped.items():
        value = params.get(source_param)
        range_slots = [slot for slot in source_slots if slot.get("bound_part")]
        if range_slots:
            range_slots.sort(key=lambda slot: slot.get("bound_part") != "start")
            replacement = " 至 ".join(f"[{slot['id']}]" for slot in range_slots)
            if isinstance(value, str) and value.strip():
                redacted = re.sub(re.escape(value), replacement, redacted, flags=re.IGNORECASE)
            continue
        slot = source_slots[0]
        if isinstance(value, str) and value.strip():
            redacted = re.sub(re.escape(value), f"[{slot['id']}]", redacted, flags=re.IGNORECASE)
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            redacted = redacted.replace(str(value), f"[{slot['id']}]")
    return redacted


def bound_input_params(
    merged_params: dict[str, Any],
    filter_specs: list[dict[str, Any]],
    slots: list[dict[str, str]],
) -> dict[str, Any]:
    """Bind opaque SQL slots only after SQL planning is complete."""
    specs_by_name = {
        str(spec.get("name")): spec
        for spec in filter_specs
        if isinstance(spec, dict) and spec.get("name")
    }
    bound: dict[str, Any] = {}
    range_cache: dict[str, tuple[str, str]] = {}
    for slot in slots:
        source_name = slot.get("source_param")
        if source_name not in merged_params:
            continue
        value = merged_params[source_name]
        if slot.get("bound_part"):
            if source_name not in range_cache:
                spec = specs_by_name.get(str(source_name), {})
                range_cache[source_name] = resolve_range_value(value, str(spec.get("value_type") or ""))
            bound[slot["id"]] = range_cache[source_name][0 if slot["bound_part"] == "start" else 1]
        else:
            bound[slot["id"]] = value
    return bound


def resolve_range_value(value: Any, _value_type: str = "") -> tuple[str, str]:
    """Normalize a generic range into ISO bounds before SQL execution."""
    if isinstance(value, dict) and value.get("start") is not None and value.get("end") is not None:
        return str(value["start"]), str(value["end"])
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return str(value[0]), str(value[1])
    if not isinstance(value, str):
        raise TypeError("range filter requires two bounds or a temporal expression")
    text = " ".join(value.split()).strip()
    text = re.sub(r"的$", "", text)
    explicit = re.findall(r"\d{4}-\d{1,2}-\d{1,2}", text)
    if len(explicit) == 2:
        return explicit[0], explicit[1]
    today = datetime.now().astimezone().date()
    if text in {"今年上半年", "本年上半年", "上半年"}:
        return date(today.year, 1, 1).isoformat(), date(today.year, 7, 1).isoformat()
    if text in {"今年下半年", "本年下半年", "下半年"}:
        return date(today.year, 7, 1).isoformat(), date(today.year + 1, 1, 1).isoformat()
    if text in {"去年上半年", "上一年上半年"}:
        return date(today.year - 1, 1, 1).isoformat(), date(today.year - 1, 7, 1).isoformat()
    if text in {"去年下半年", "上一年下半年"}:
        return date(today.year - 1, 7, 1).isoformat(), date(today.year, 1, 1).isoformat()
    if text in {"本月", "这个月", "this month"}:
        start = today.replace(day=1)
        end = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        return start.isoformat(), end.isoformat()
    if text in {"上月", "上个月", "last month"}:
        end = today.replace(day=1)
        previous_month = (end - timedelta(days=1)).replace(day=1)
        return previous_month.isoformat(), end.isoformat()
    if text in {"今年", "本年", "这一年", "本年度", "this year"}:
        return date(today.year, 1, 1).isoformat(), date(today.year + 1, 1, 1).isoformat()
    if text in {"去年", "上一年", "上年度", "last year"}:
        return date(today.year - 1, 1, 1).isoformat(), date(today.year, 1, 1).isoformat()
    relative = re.fullmatch(
        r"(?:最近|近|过去|last|past)\s*(\d+|[零一二两三四五六七八九十百]+)\s*"
        r"(天|日|days?|周|weeks?|月|个月|months?|年|years?)",
        text,
        re.IGNORECASE,
    )
    if relative:
        amount = parse_count(relative.group(1))
        unit = relative.group(2).lower()
        if unit in {"月", "个月", "month", "months"}:
            month = today.month - amount
            year = today.year + (month - 1) // 12
            month = (month - 1) % 12 + 1
            day = min(today.day, monthrange(year, month)[1])
            start = date(year, month, day)
        elif unit in {"年", "year", "years"}:
            year = today.year - amount
            start = date(year, today.month, min(today.day, monthrange(year, today.month)[1]))
        elif unit in {"周", "week", "weeks"}:
            start = today - timedelta(weeks=amount)
        else:
            start = today - timedelta(days=amount)
        return start.isoformat(), (today + timedelta(days=1)).isoformat()
    raise ValueError(f"无法解析时间范围: {value}")


def parse_count(value: str) -> int:
    """Parse the small numeric vocabulary used by relative ranges."""
    if value.isdigit():
        return int(value)
    digits = {"零": 0, "一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if value == "十":
        return 10
    if value.startswith("十"):
        return 10 + digits.get(value[1:], 0)
    if value.endswith("十"):
        return digits.get(value[:-1], 0) * 10
    if "十" in value:
        left, right = value.split("十", 1)
        return digits.get(left, 0) * 10 + digits.get(right, 0)
    if value in digits:
        return digits[value]
    raise ValueError(f"无法解析数量: {value}")
