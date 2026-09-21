"""选择后续查询应参考的安全历史查询候选。

候选只包含脱敏 goal、参数化 SQL 和结果结构，不包含结果行或私有分析。
这里使用保守的确定性校验：无法唯一确定时返回 clarification，而不是猜一条。
"""
from __future__ import annotations

import re
from typing import Any, Literal


SelectionStatus = Literal["none", "selected", "ambiguous"]

_FOLLOWUP_MARKERS = (
    "排序",
    "只看",
    "改成",
    "换成",
    "再加",
    "添加",
    "刚才",
    "继续",
    "分组",
    "拆分",
    "展开",
    "明细",
    "详细",
    "筛选",
    "过滤",
    "the previous",
    "sort",
    "order",
    "only",
)
_HISTORICAL_REFERENCE_MARKERS = (
    "刚才的查询",
    "之前的查询",
    "上次的查询",
    "上一条查询",
    "历史查询",
    "之前的结果",
    "刚才的结果",
    "上次的结果",
    "以前的查询",
    "以前的结果",
    "这两个结果",
    "这两条结果",
    "两个查询",
    "两次查询",
)
_LATEST_QUERY_MARKERS = (
    "刚才查询",
    "刚才的查询",
    "刚刚查询",
    "刚刚的查询",
    "最近一次查询",
    "最近一次的查询",
    "上一次查询",
    "上一次的查询",
    "上一条查询",
    "刚才的结果",
    "刚刚的结果",
    "最近一次结果",
    "上一次的结果",
)
_STOP_WORDS = {
    "查询", "统计", "分析", "查看", "请", "帮我", "一下", "记录", "数据", "结果",
    "近", "最近", "按照", "进行", "这个", "那个", "的", "和", "与", "并", "再",
}
_CHINESE_NUMBERS = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
}


def parse_candidate_reply(query: str) -> int | None:
    """解析用户对澄清问题的候选编号回复。"""
    text = str(query or "").strip().casefold()
    match = re.search(r"第\s*([1-9][0-9]*)\s*(?:个|条|项|次)?", text)
    if match:
        return int(match.group(1))
    match = re.search(r"第\s*([一二两三四五])\s*(?:个|条|项|次)", text)
    if match:
        return _CHINESE_NUMBERS[match.group(1)]
    match = re.search(r"(?:候选|选择|选)\s*([1-9][0-9]*)", text)
    return int(match.group(1)) if match else None


def _tokens(value: str) -> set[str]:
    """提取用于候选比较的低敏感度词元。"""
    text = str(value or "").casefold()
    tokens: set[str] = set(re.findall(r"[a-z][a-z0-9_]*", text))
    for run in re.findall(r"[\u4e00-\u9fff]+", text):
        if run not in _STOP_WORDS and len(run) >= 2:
            tokens.add(run)
        tokens.update(
            run[index:index + 2]
            for index in range(len(run) - 1)
            if run[index:index + 2] not in _STOP_WORDS
        )
    return {token for token in tokens if token not in _STOP_WORDS}


def _candidate_text(entry: dict[str, Any]) -> str:
    fields = entry.get("fields") or []
    return " ".join(
        [
            str(entry.get("goal") or ""),
            str(entry.get("name") or ""),
            str(entry.get("sql_template") or ""),
            " ".join(str(field) for field in fields),
        ]
    )


def _score(current_text: str, entry: dict[str, Any]) -> int:
    current = _tokens(current_text)
    candidate = _tokens(_candidate_text(entry))
    overlap = current & candidate
    score = len(overlap)

    # 完整的脱敏历史目标是最可靠的匹配信号。
    goal = str(entry.get("goal") or "").strip().casefold()
    normalized_current = " ".join(current_text.casefold().split())
    if goal and goal in normalized_current:
        score += 4
    return score


def _is_followup(query: str) -> bool:
    lowered = str(query or "").casefold()
    if is_counted_result_reference(lowered):
        return True
    if any(marker.casefold() in lowered for marker in _FOLLOWUP_MARKERS):
        return True
    return bool(re.search(r"(?:按|按照).*(?:排序|拆分|分组|筛选|过滤)", lowered))


def is_counted_result_reference(user_query: str) -> bool:
    """Recognize references such as ``把这98笔都列给我``.

    The count is a confirmation of the immediately preceding result; the
    query should not need to repeat the words "交易" or "订单".
    """
    text = str(user_query or "").strip().casefold()
    number = r"(?:[0-9]+|[一二两三四五六七八九十百千万]+)"
    return bool(re.search(rf"(?:这|该|上述)\s*{number}\s*笔", text))


def is_explicit_query_continuation(user_query: str) -> bool:
    """Return whether the user explicitly asks to continue a prior query.

    Query history is opt-in.  A standalone request such as ``统计上个月的
    交易`` must not inherit the previous query merely because the session has
    one.  Transformation requests (``按金额排序``) remain valid follow-ups,
    while relative time phrases such as ``上一年`` do not match any history
    marker by themselves.
    """
    text = str(user_query or "").strip().casefold()
    if not text:
        return False
    if parse_candidate_reply(text) is not None:
        return True
    if is_explicit_historical_reference(text, text):
        return True
    if is_counted_result_reference(text):
        return True
    if _is_followup(text):
        return True
    return bool(
        re.search(
            r"(?:这(?:批|些|\s*\d+\s*笔|\s*[一二两三四五六七八九十百千万]+\s*笔)|该|上述|它们).{0,12}(?:订单|交易|结果|记录|查询|数据)",
            text,
        )
    )


def is_explicit_historical_reference(current_goal: str, user_query: str) -> bool:
    """Distinguish historical-result comparison from multi-angle analysis.

    This is a safety boundary for the structured reference field, not the
    primary router.  A request such as "从多个方面分析" must remain a new
    analysis over one dataset; multiple query ids are reserved for an
    explicitly named historical comparison.
    """
    text = f"{current_goal} {user_query}".casefold()
    return any(marker.casefold() in text for marker in _HISTORICAL_REFERENCE_MARKERS)


def _requests_latest_query(user_query: str) -> bool:
    lowered = str(user_query or "").casefold()
    return any(marker.casefold() in lowered for marker in _LATEST_QUERY_MARKERS)


def select_query_candidate(
    entries: list[dict[str, Any]],
    *,
    candidate: int | None,
    current_goal: str,
    user_query: str,
    query_ids: list[str] | None = None,
    confirmed_candidate: int | None = None,
) -> dict[str, Any]:
    """返回安全历史查询候选的选择结果。

    ``candidate`` 是第一层 LLM 提供的本次上下文编号，不是 result_ref。
    选择结果只供后端绑定参数化 SQL，不会暴露给普通 LLM。
    """
    if not entries:
        if candidate is not None or _is_followup(user_query):
            return {
                "status": "ambiguous",
                "selected_candidate": None,
                "ranked": [],
                "message": "当前会话没有可供参考的历史查询，请补充完整的查询对象。",
            }
        return {"status": "none", "selected_candidate": None, "ranked": []}

    ranked = sorted(
        [
            {
                "query_candidate": entry.get("query_candidate"),
                "query_id": entry.get("query_id"),
                "goal": entry.get("goal") or entry.get("name") or "历史查询",
                "score": _score(f"{current_goal} {user_query}", entry),
            }
            for entry in entries
        ],
        key=lambda item: (-item["score"], item["query_candidate"] or 0),
    )
    top = ranked[0]
    second_score = ranked[1]["score"] if len(ranked) > 1 else -1
    margin = top["score"] - second_score

    requested_query_ids = [str(item) for item in (query_ids or []) if str(item).strip()]
    if _requests_latest_query(user_query) or is_counted_result_reference(user_query):
        # "刚才查询/刚才的结果" is an ordinal reference, not a semantic
        # search.  The context projection is already ordered newest first;
        # do not let the model select an older query because its SQL happens
        # to share more words with "展开明细".
        latest = next(
            (item for item in ranked if item.get("query_candidate") == entries[0].get("query_candidate")),
            None,
        )
        if latest is not None:
            return {
                "status": "selected",
                "selected_candidate": latest["query_candidate"],
                "selected_query_id": latest.get("query_id"),
                "selected_query_ids": [str(latest.get("query_id"))] if latest.get("query_id") else [],
                "selected_goal": latest.get("goal") or "",
                "resolution": "counted_latest" if is_counted_result_reference(user_query) else "latest",
                "ranked": ranked,
            }
    if requested_query_ids:
        if len(requested_query_ids) > 1:
            matched = [
                item
                for item in ranked
                if str(item.get("query_id") or "") in requested_query_ids
            ]
            if len(matched) != len(requested_query_ids):
                message = "部分历史查询无法在当前会话中定位，请重新选择查询。"
            else:
                message = "当前查询一次只能展开一条历史查询，请先选择具体的查询。"
            return {
                "status": "ambiguous",
                "selected_candidate": None,
                "selected_query_id": None,
                "ranked": ranked,
                "message": message,
            }
        selected = next(
            (item for item in ranked if str(item.get("query_id") or "") in requested_query_ids),
            None,
        )
        if selected is None:
            return {
                "status": "ambiguous",
                "selected_candidate": None,
                "selected_query_id": None,
                "ranked": ranked,
                "message": "引用的历史查询已不存在或不属于当前会话，请重新说明查询条件。",
            }
        return {
            "status": "selected",
            "selected_candidate": selected["query_candidate"],
            "selected_query_id": selected.get("query_id"),
            "selected_query_ids": requested_query_ids,
            "ranked": ranked,
        }

    if confirmed_candidate is not None:
        selected = next((item for item in ranked if item["query_candidate"] == confirmed_candidate), None)
        if selected is not None:
            return {
                "status": "selected",
                "selected_candidate": confirmed_candidate,
                "selected_query_id": selected.get("query_id"),
                "ranked": ranked,
            }

    if candidate is not None:
        selected = next((item for item in ranked if item["query_candidate"] == candidate), None)
        if selected is None:
            return {
                "status": "ambiguous",
                "selected_candidate": None,
                "ranked": ranked,
                "message": "引用的历史查询候选已不存在，请重新说明要修改哪一次查询。",
            }
        if len(ranked) == 1 or (selected["query_candidate"] == top["query_candidate"] and selected["score"] >= 2 and margin >= 2):
            return {
                "status": "selected",
                "selected_candidate": candidate,
                "selected_query_id": selected.get("query_id"),
                "ranked": ranked,
            }
    elif _is_followup(user_query) and len(ranked) == 1:
        return {
            "status": "selected",
            "selected_candidate": top["query_candidate"],
            "selected_query_id": top.get("query_id"),
            "ranked": ranked,
        }
    elif _is_followup(user_query) and top["score"] >= 2 and margin >= 2:
        return {
            "status": "selected",
            "selected_candidate": top["query_candidate"],
            "selected_query_id": top.get("query_id"),
            "ranked": ranked,
        }
    elif not _is_followup(user_query):
        return {"status": "none", "selected_candidate": None, "ranked": ranked}

    labels = [f"第{item['query_candidate']}个：{item['goal']}" for item in ranked[:3]]
    return {
        "status": "ambiguous",
        "selected_candidate": None,
        "ranked": ranked,
        "message": "我找到多个可能的历史查询，无法确定你要修改哪一个："
        + "；".join(labels)
        + "。请告诉我具体是第几个，或补充查询对象。",
    }
