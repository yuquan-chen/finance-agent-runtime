"""Session Manager — 管理会话的持久化存储。

每个 session 一个 JSON 文件，存储在 data/sessions/ 目录。
支持多 session、对话历史持久化、session 切换。
"""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


class SessionManager:
    """Session 管理器，负责 session 的 CRUD 操作。"""

    def __init__(self, sessions_dir: Path | str | None = None):
        if sessions_dir is None:
            sessions_dir = Path(__file__).parent.parent.parent.parent / "data" / "sessions"
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def _session_path(self, session_id: str) -> Path:
        """获取 session 文件路径。"""
        return self.sessions_dir / f"{session_id}.json"

    def create_session(self, title: str | None = None) -> dict[str, Any]:
        """创建新的 session。"""
        session_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        session_data = {
            "session_id": session_id,
            "title": title or f"对话 {now[:10]}",
            "created_at": now,
            "updated_at": now,
            "conversation_history": [],
            # 用户界面按发生顺序恢复的事件索引。真实结果仍只保存在
            # private_analysis，时间线只保存其 analysis_id，不会进入 LLM 上下文。
            "timeline": [],
            # 当前用户可见的真实结果与解读；不属于普通模型上下文。
            "private_analysis": [],
            # 待确认的计划/方法仅保存安全的 UI 数据，不保存执行结果。
            "pending_review": None,
            # 待确认运行的可恢复状态；不包含执行后的真实结果。
            "pending_run_state": None,
            # 历史查询候选澄清状态；只保存安全 goal/候选编号，不保存结果行。
            "pending_query_candidate": None,
            # 右侧运行详情仅保存最近一次运行的安全追踪，不保存结果行。
            "run_detail": None,
            "metadata": {},
        }

        # 保存到文件
        self._session_path(session_id).write_text(
            json.dumps(session_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return session_data

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """获取 session 数据。"""
        path = self._session_path(session_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def list_sessions(self) -> list[dict[str, Any]]:
        """列出所有 session。"""
        sessions = []
        for path in self.sessions_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                sessions.append({
                    "session_id": data["session_id"],
                    "title": data.get("title", ""),
                    "created_at": data.get("created_at", ""),
                    "updated_at": data.get("updated_at", ""),
                    "pinned": bool(data.get("metadata", {}).get("pinned", False)),
                    "message_count": len(data.get("conversation_history", [])),
                })
            except Exception:
                continue
        # 文件名是随机 UUID，不能代表对话的新旧；按最近更新时间展示。
        return sorted(sessions, key=lambda session: (session["pinned"], session["updated_at"]), reverse=True)

    def set_session_pinned(self, session_id: str, pinned: bool) -> dict[str, Any] | None:
        """设置会话是否置顶，不改变对话内容。"""
        session_data = self.get_session(session_id)
        if session_data is None:
            return None
        metadata = dict(session_data.get("metadata") or {})
        metadata["pinned"] = pinned
        return self.update_session(session_id, {"metadata": metadata})

    def update_session(self, session_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        """更新 session 数据。"""
        session_data = self.get_session(session_id)
        if session_data is None:
            return None

        # 更新字段
        for key, value in updates.items():
            if key != "session_id":  # 不允许修改 session_id
                session_data[key] = value

        # 更新时间
        session_data["updated_at"] = datetime.now().isoformat()

        # 保存到文件
        self._session_path(session_id).write_text(
            json.dumps(session_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return session_data

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        request_id: str | None = None,
    ) -> dict[str, Any] | None:
        """添加消息到对话历史。"""
        session_data = self.get_session(session_id)
        if session_data is None:
            return None

        # 添加消息
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }
        if request_id:
            message["request_id"] = request_id
        session_data["conversation_history"].append(message)
        session_data.setdefault("timeline", []).append(
            {
                "kind": "message",
                "role": role,
                "content": content,
                "request_id": request_id,
                "timestamp": message["timestamp"],
            }
        )

        # 更新时间
        session_data["updated_at"] = datetime.now().isoformat()

        # 自动更新标题（如果是第一条用户消息）
        if role == "user" and len(session_data["conversation_history"]) == 1:
            session_data["title"] = content[:50] + ("..." if len(content) > 50 else "")

        # 保存到文件
        self._session_path(session_id).write_text(
            json.dumps(session_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return session_data

    def add_private_analysis(self, session_id: str, analysis: dict[str, Any]) -> dict[str, Any] | None:
        """保存当前用户可见的真实结果与解读，不写入普通 conversation_history。"""
        session_data = self.get_session(session_id)
        if session_data is None:
            return None

        entry = {
            "analysis_id": analysis.get("analysis_id") or f"analysis_{uuid.uuid4().hex}",
            "request_id": analysis.get("request_id", ""),
            "answer": analysis.get("answer", ""),
            "result_ref": analysis.get("result_ref"),
            "result_refs": list(analysis.get("result_refs") or []),
            "plan_result_ref": analysis.get("plan_result_ref"),
            "execution_result_card": analysis.get("execution_result_card"),
            "execution_result_cards": list(analysis.get("execution_result_cards") or []),
            "result_narration": analysis.get("result_narration"),
            "result_narrations": list(analysis.get("result_narrations") or []),
            "created_at": analysis.get("created_at") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        session_data.setdefault("private_analysis", []).append(entry)
        session_data.setdefault("timeline", []).append(
            {
                "kind": "private_analysis",
                "analysis_id": entry["analysis_id"],
                # created_at is UTC for result records; this timestamp follows the
                # same clock as ordinary chat messages and is only for diagnostics.
                "timestamp": datetime.now().isoformat(),
            }
        )
        session_data["updated_at"] = datetime.now().isoformat()
        self._session_path(session_id).write_text(
            json.dumps(session_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return entry

    def get_private_analysis(self, session_id: str, limit: int | None = None) -> list[dict[str, Any]]:
        """获取当前用户可见的私有分析；该数据不送入任何普通 LLM。"""
        session_data = self.get_session(session_id)
        if session_data is None:
            return []
        analyses = session_data.get("private_analysis", [])
        if not isinstance(analyses, list):
            return []
        return analyses[-limit:] if limit is not None else analyses

    def get_timeline(self, session_id: str) -> list[dict[str, Any]]:
        """获取供 UI 恢复的有序事件流，不可用于构造 LLM 上下文。"""
        session_data = self.get_session(session_id)
        if session_data is None:
            return []
        timeline = session_data.get("timeline")
        if isinstance(timeline, list) and timeline:
            if self._backfill_legacy_review_cards(session_data, timeline):
                self._session_path(session_id).write_text(
                    json.dumps(session_data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            return timeline

        # 兼容升级前的会话：根据已有的落盘时间补建一次事件索引。普通消息
        # 使用本地时间，私有结果使用 UTC 时间；统一转换为时间戳后即可恢复
        # 它们原本的相对位置。
        events: list[dict[str, Any]] = []
        for message in session_data.get("conversation_history", []):
            events.append({"kind": "message", **message})
        for analysis in session_data.get("private_analysis", []):
            events.append(
                {
                    "kind": "private_analysis",
                    "analysis_id": analysis.get("analysis_id"),
                    "timestamp": analysis.get("created_at", ""),
                }
            )
        local_timezone = datetime.now().astimezone().tzinfo

        def event_timestamp(event: dict[str, Any]) -> float:
            raw_timestamp = str(event.get("timestamp") or "")
            try:
                parsed = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=local_timezone)
                return parsed.timestamp()
            except ValueError:
                return float("inf")

        events.sort(key=event_timestamp)
        if events:
            session_data["timeline"] = events
            self._backfill_legacy_review_cards(session_data, events)
            self._session_path(session_id).write_text(
                json.dumps(session_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return events

    @staticmethod
    def _backfill_legacy_review_cards(
        session_data: dict[str, Any],
        timeline: list[dict[str, Any]],
    ) -> bool:
        """从旧执行结果补出已确认的只读卡片，不暴露额外结果数据。"""
        analyses = {
            str(item.get("analysis_id")): item
            for item in session_data.get("private_analysis", [])
            if item.get("analysis_id")
        }
        changed = False
        for index, event in enumerate(timeline):
            if event.get("kind") != "private_analysis":
                continue
            analysis = analyses.get(str(event.get("analysis_id")))
            if not analysis:
                continue
            for previous in reversed(timeline[:index]):
                if previous.get("kind") != "message" or previous.get("role") != "assistant":
                    continue
                if previous.get("review"):
                    break
                card = analysis.get("execution_result_card") or {}
                authorization = card.get("data_authorization") or {}
                evidence = card.get("evidence") or {}
                method = {
                    "method_type": evidence.get("method_type", "sql"),
                    "name": card.get("method_name", "受控数据查询"),
                    "goal": authorization.get("purpose", "已执行分析"),
                    "required_fields": list(authorization.get("fields") or []),
                    "sql_template": evidence.get("sql_template"),
                    "logic_summary": [],
                }
                previous["request_id"] = analysis.get("request_id") or previous.get("request_id")
                previous["review"] = {
                    "request_id": analysis.get("request_id", ""),
                    "status": "executed_simulated_real",
                    "method_draft": method,
                    "method_drafts": [method],
                    "method_review_card": {
                        "method_name": method["name"],
                        "method_type": method["method_type"],
                        "goal": method["goal"],
                        "required_fields": method["required_fields"],
                        "logic_summary": [],
                    },
                }
                changed = True
                break
        return changed

    def set_review_snapshot(
        self,
        session_id: str,
        request_id: str,
        review: dict[str, Any],
    ) -> bool:
        """把确认卡快照绑定到其对应的 assistant 时间线事件。"""
        session_data = self.get_session(session_id)
        if session_data is None:
            return False
        fallback: dict[str, Any] | None = None
        for event in reversed(session_data.get("timeline") or []):
            if event.get("kind") == "message" and event.get("role") == "assistant" and fallback is None:
                fallback = event
            if (
                event.get("kind") == "message"
                and event.get("role") == "assistant"
                and event.get("request_id") == request_id
            ):
                event["review"] = review
                self._session_path(session_id).write_text(
                    json.dumps(session_data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                return True
        # 升级前的 assistant 消息没有 request_id；待确认卡只能对应当时最后
        # 一条 assistant 消息，因此可安全地在此补上关联。
        if fallback is not None:
            fallback["request_id"] = request_id
            fallback["review"] = review
            self._session_path(session_id).write_text(
                json.dumps(session_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return True
        return False

    def set_review_status(
        self,
        session_id: str,
        request_id: str,
        status: str,
        *,
        review_id: str | None = None,
    ) -> bool:
        """更新最近一张确认卡的最终状态，保留原始审查范围。"""
        session_data = self.get_session(session_id)
        if session_data is None:
            return False
        for event in reversed(session_data.get("timeline") or []):
            review = event.get("review") or {}
            if (
                event.get("kind") == "message"
                and event.get("request_id") == request_id
                and review
                and (review_id is None or review.get("review_id") == review_id)
            ):
                review["status"] = status
                event["review"] = review
                self._session_path(session_id).write_text(
                    json.dumps(session_data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                return True
        return False

    def set_pending_review(self, session_id: str, review: dict[str, Any] | None) -> dict[str, Any] | None:
        """保存或清除会话中尚未确认的安全审查卡片数据。"""
        return self.update_session(session_id, {"pending_review": review})

    def get_pending_review(self, session_id: str) -> dict[str, Any] | None:
        session_data = self.get_session(session_id)
        if session_data is None:
            return None
        review = session_data.get("pending_review")
        return review if isinstance(review, dict) else None

    def set_pending_run_state(self, session_id: str, state: dict[str, Any] | None) -> dict[str, Any] | None:
        """持久化可恢复的待确认运行状态，不保存执行结果行。"""
        return self.update_session(session_id, {"pending_run_state": state})

    def get_pending_run_state(self, session_id: str) -> dict[str, Any] | None:
        session_data = self.get_session(session_id)
        if session_data is None:
            return None
        state = session_data.get("pending_run_state")
        return state if isinstance(state, dict) else None

    def set_pending_query_candidate(self, session_id: str, state: dict[str, Any] | None) -> dict[str, Any] | None:
        """保存或清除历史查询候选澄清状态。"""
        return self.update_session(session_id, {"pending_query_candidate": state})

    def get_pending_query_candidate(self, session_id: str) -> dict[str, Any] | None:
        session_data = self.get_session(session_id)
        if session_data is None:
            return None
        state = session_data.get("pending_query_candidate")
        return state if isinstance(state, dict) else None

    def set_run_detail(self, session_id: str, detail: dict[str, Any] | None) -> dict[str, Any] | None:
        """保存或清除右侧面板的安全运行追踪。"""
        return self.update_session(session_id, {"run_detail": detail})

    def get_run_detail(self, session_id: str) -> dict[str, Any] | None:
        session_data = self.get_session(session_id)
        if session_data is None:
            return None
        detail = session_data.get("run_detail")
        return detail if isinstance(detail, dict) else None

    def delete_session(self, session_id: str) -> bool:
        """删除 session。"""
        path = self._session_path(session_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def get_conversation_history(self, session_id: str, limit: int | None = None) -> list[dict[str, Any]]:
        """获取对话历史。"""
        session_data = self.get_session(session_id)
        if session_data is None:
            return []

        history = session_data.get("conversation_history", [])
        if limit is not None:
            history = history[-limit:]

        return history


# 默认实例
_default_manager: SessionManager | None = None


def get_session_manager() -> SessionManager:
    """获取默认的 SessionManager 实例。"""
    global _default_manager
    if _default_manager is None:
        _default_manager = SessionManager()
    return _default_manager
