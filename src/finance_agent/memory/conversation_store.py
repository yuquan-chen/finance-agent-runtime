"""对话历史持久化存储。

保存所有用户消息和 AI 回复，支持跨 session 查询。
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ConversationTurn:
    """单轮对话。"""
    role: str  # "user" | "assistant"
    content: str
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConversationTurn:
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=data.get("timestamp", ""),
            metadata=data.get("metadata", {}),
        )


class ConversationStore:
    """对话历史存储。"""

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_session_file(self, session_id: str | None = None) -> Path:
        """获取 session 文件路径。"""
        if session_id:
            return self.base_path / f"{session_id}.jsonl"
        # 默认使用当前日期作为文件名
        date_str = time.strftime("%Y-%m-%d")
        return self.base_path / f"{date_str}.jsonl"

    def add_turn(
        self,
        role: str,
        content: str,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ConversationTurn:
        """添加一轮对话。"""
        turn = ConversationTurn(
            role=role,
            content=content,
            metadata=metadata or {},
        )

        # 追加到文件
        file_path = self._get_session_file(session_id)
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(turn.to_dict(), ensure_ascii=False) + "\n")

        return turn

    def get_recent_turns(
        self,
        limit: int = 10,
        session_id: str | None = None,
    ) -> list[ConversationTurn]:
        """获取最近的对话轮次。"""
        file_path = self._get_session_file(session_id)
        if not file_path.exists():
            return []

        turns = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        turns.append(ConversationTurn.from_dict(data))
                    except json.JSONDecodeError:
                        continue

        # 返回最近的 N 条
        return turns[-limit:]

    def get_all_sessions(self) -> list[str]:
        """获取所有 session ID。"""
        sessions = []
        for file_path in self.base_path.glob("*.jsonl"):
            sessions.append(file_path.stem)
        return sorted(sessions)

    def get_session_turns(self, session_id: str) -> list[ConversationTurn]:
        """获取指定 session 的所有对话。"""
        return self.get_recent_turns(limit=1000, session_id=session_id)

    def clear_session(self, session_id: str) -> bool:
        """清空指定 session。"""
        file_path = self._get_session_file(session_id)
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def clear_all(self) -> int:
        """清空所有对话历史。"""
        count = 0
        for file_path in self.base_path.glob("*.jsonl"):
            file_path.unlink()
            count += 1
        return count
