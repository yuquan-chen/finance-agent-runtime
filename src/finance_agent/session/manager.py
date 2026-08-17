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
            # 当前用户可见的真实结果与解读；不属于普通模型上下文。
            "private_analysis": [],
            # 待确认的计划/方法仅保存安全的 UI 数据，不保存执行结果。
            "pending_review": None,
            # 待确认运行的可恢复状态；不包含执行后的真实结果。
            "pending_run_state": None,
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

    def add_message(self, session_id: str, role: str, content: str) -> dict[str, Any] | None:
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
        session_data["conversation_history"].append(message)

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
