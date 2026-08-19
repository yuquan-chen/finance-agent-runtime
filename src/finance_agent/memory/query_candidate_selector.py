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
    "上一",
    "之前",
    "继续",
    "分组",
    "拆分",
    "the previous",
    "sort",
    "order",
    "only",
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
    if any(marker.casefold() in lowered for marker in _FOLLOWUP_MARKERS):
        return True
    return bool(re.search(r"(?:按|按照).*(?:排序|拆分|分组|筛选|过滤)", lowered))


def select_query_candidate(
    entries: list[dict[str, Any]],
    *,
    candidate: int | None,
    current_goal: str,
    user_query: str,
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

    if confirmed_candidate is not None:
        selected = next((item for item in ranked if item["query_candidate"] == confirmed_candidate), None)
        if selected is not None:
            return {
                "status": "selected",
                "selected_candidate": confirmed_candidate,
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
            return {"status": "selected", "selected_candidate": candidate, "ranked": ranked}
    elif _is_followup(user_query) and len(ranked) == 1:
        return {"status": "selected", "selected_candidate": top["query_candidate"], "ranked": ranked}
    elif _is_followup(user_query) and top["score"] >= 2 and margin >= 2:
        return {"status": "selected", "selected_candidate": top["query_candidate"], "ranked": ranked}
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
