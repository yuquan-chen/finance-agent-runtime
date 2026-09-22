"""Durable side-thread storage.

Side conversations are first-class threads rather than nested dictionaries in a
parent session document. The event log is the source of a side thread's
conversation; workflow artifacts are separate, versioned shared resources.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class ThreadStoreError(ValueError):
    """Raised when a thread operation cannot be completed safely."""


class WorkflowConflictError(ThreadStoreError):
    """Raised when a workflow artifact changed after a handler read it."""


RESUMABLE_STATUSES = frozenset({"active", "waiting_user", "waiting_confirmation"})
THREAD_STATUSES = frozenset({*RESUMABLE_STATUSES, "completed", "failed", "cancelled"})
_ALLOWED_TRANSITIONS = {
    "active": {"waiting_user", "waiting_confirmation", "completed", "failed", "cancelled"},
    "waiting_user": {"active", "cancelled", "failed"},
    "waiting_confirmation": {"active", "completed", "cancelled", "failed"},
    "completed": set(),
    "failed": {"active", "cancelled"},
    "cancelled": set(),
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _load(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


class SideThreadStore:
    """SQLite store for side threads, their append-only events, and artifacts."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS side_threads (
                    thread_id TEXT PRIMARY KEY,
                    parent_session_id TEXT NOT NULL,
                    skill_id TEXT NOT NULL,
                    state_key TEXT NOT NULL,
                    handler_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    context_snapshot TEXT NOT NULL,
                    checkpoint_ref TEXT,
                    version INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_side_threads_parent
                    ON side_threads(parent_session_id, updated_at DESC);

                CREATE TABLE IF NOT EXISTS side_thread_events (
                    thread_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(thread_id, sequence),
                    FOREIGN KEY(thread_id) REFERENCES side_threads(thread_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS workflow_artifacts (
                    parent_session_id TEXT NOT NULL,
                    artifact_key TEXT NOT NULL,
                    state TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(parent_session_id, artifact_key)
                );
                """
            )

    @staticmethod
    def _thread_from_row(row: sqlite3.Row, *, messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        thread = {
            "skill_session_id": row["thread_id"],
            "thread_id": row["thread_id"],
            "parent_session_id": row["parent_session_id"],
            "skill_id": row["skill_id"],
            "state_key": row["state_key"],
            "handler_id": row["handler_id"],
            "status": row["status"],
            "context": _load(row["context_snapshot"], {}),
            "context_snapshot": _load(row["context_snapshot"], {}),
            "checkpoint_ref": row["checkpoint_ref"],
            "version": int(row["version"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        if messages is not None:
            thread["messages"] = messages
        return thread

    @staticmethod
    def _messages(connection: sqlite3.Connection, thread_id: str) -> list[dict[str, Any]]:
        rows = connection.execute(
            """
            SELECT event_type, payload, created_at
            FROM side_thread_events
            WHERE thread_id = ? AND event_type IN ('user_message', 'assistant_message')
            ORDER BY sequence
            """,
            (thread_id,),
        ).fetchall()
        messages: list[dict[str, Any]] = []
        for row in rows:
            payload = _load(row["payload"], {})
            message = {
                "role": "user" if row["event_type"] == "user_message" else "assistant",
                "content": str(payload.get("content") or ""),
                "timestamp": row["created_at"],
            }
            if payload.get("attachments"):
                message["attachments"] = payload["attachments"]
            messages.append(message)
        return messages

    @staticmethod
    def _append_event(
        connection: sqlite3.Connection,
        thread_id: str,
        event_type: str,
        payload: dict[str, Any],
        *,
        created_at: str | None = None,
    ) -> int:
        row = connection.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 AS next_sequence FROM side_thread_events WHERE thread_id = ?",
            (thread_id,),
        ).fetchone()
        sequence = int(row["next_sequence"])
        connection.execute(
            "INSERT INTO side_thread_events(thread_id, sequence, event_type, payload, created_at) VALUES (?, ?, ?, ?, ?)",
            (thread_id, sequence, event_type, _json(payload), created_at or _now()),
        )
        return sequence

    def thread_exists(self, thread_id: str) -> bool:
        with self._connect() as connection:
            return connection.execute("SELECT 1 FROM side_threads WHERE thread_id = ?", (thread_id,)).fetchone() is not None

    def create_thread(
        self,
        *,
        thread_id: str,
        parent_session_id: str,
        skill_id: str,
        state_key: str,
        handler_id: str,
        context_snapshot: dict[str, Any],
        status: str = "active",
        created_at: str | None = None,
    ) -> dict[str, Any]:
        if status not in THREAD_STATUSES:
            raise ThreadStoreError(f"unsupported thread status: {status}")
        now = created_at or _now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO side_threads(
                    thread_id, parent_session_id, skill_id, state_key, handler_id, status,
                    context_snapshot, checkpoint_ref, version, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 1, ?, ?)
                """,
                (thread_id, parent_session_id, skill_id, state_key, handler_id, status, _json(context_snapshot), now, now),
            )
            self._append_event(
                connection,
                thread_id,
                "thread_created",
                {"parent_session_id": parent_session_id, "skill_id": skill_id, "handler_id": handler_id, "status": status},
                created_at=now,
            )
            row = connection.execute("SELECT * FROM side_threads WHERE thread_id = ?", (thread_id,)).fetchone()
            connection.commit()
        return self._thread_from_row(row, messages=[])

    def import_legacy_thread(self, thread: dict[str, Any]) -> None:
        """Import an old nested skill session once, without mutating its JSON source."""
        thread_id = str(thread.get("skill_session_id") or "")
        if not thread_id or self.thread_exists(thread_id):
            return
        created_at = str(thread.get("created_at") or _now())
        status = str(thread.get("status") or "active")
        if status == "closed":
            status = "cancelled"
        if status not in THREAD_STATUSES:
            status = "failed"
        imported = self.create_thread(
            thread_id=thread_id,
            parent_session_id=str(thread.get("parent_session_id") or ""),
            skill_id=str(thread.get("skill_id") or "general"),
            state_key=str(thread.get("state_key") or thread.get("skill_id") or "general"),
            handler_id=str(thread.get("handler_id") or "general"),
            context_snapshot=dict(thread.get("context") or {}),
            status=status,
            created_at=created_at,
        )
        del imported
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for message in thread.get("messages") or []:
                role = message.get("role")
                if role not in {"user", "assistant"}:
                    continue
                self._append_event(
                    connection,
                    thread_id,
                    f"{role}_message",
                    {"content": str(message.get("content") or ""), "attachments": message.get("attachments") or []},
                    created_at=str(message.get("timestamp") or _now()),
                )
            connection.commit()

    def get_thread(self, thread_id: str, *, parent_session_id: str | None = None) -> dict[str, Any] | None:
        with self._connect() as connection:
            query = "SELECT * FROM side_threads WHERE thread_id = ?"
            params: tuple[str, ...] = (thread_id,)
            if parent_session_id:
                query += " AND parent_session_id = ?"
                params = (thread_id, parent_session_id)
            row = connection.execute(query, params).fetchone()
            if row is None:
                return None
            return self._thread_from_row(row, messages=self._messages(connection, thread_id))

    def list_threads(self, parent_session_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM side_threads WHERE parent_session_id = ? ORDER BY updated_at DESC", (parent_session_id,)
            ).fetchall()
            return [self._thread_from_row(row) for row in rows]

    def begin_turn(self, thread_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM side_threads WHERE thread_id = ?", (thread_id,)).fetchone()
            if row is None:
                connection.rollback()
                raise ThreadStoreError("side thread not found")
            status = row["status"]
            if status not in RESUMABLE_STATUSES:
                connection.rollback()
                raise ThreadStoreError("side thread is not resumable")
            now = _now()
            if status != "active":
                connection.execute(
                    "UPDATE side_threads SET status = 'active', version = version + 1, updated_at = ? WHERE thread_id = ?",
                    (now, thread_id),
                )
                self._append_event(connection, thread_id, "status_changed", {"from": status, "to": "active"}, created_at=now)
            self._append_event(connection, thread_id, "turn_started", {}, created_at=now)
            updated = connection.execute("SELECT * FROM side_threads WHERE thread_id = ?", (thread_id,)).fetchone()
            connection.commit()
        return self._thread_from_row(updated, messages=[])

    def append_message(
        self,
        thread_id: str,
        role: str,
        content: str,
        attachments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        """Append an out-of-band message such as a thread opening notice."""
        if role not in {"user", "assistant"}:
            raise ThreadStoreError("side thread messages must be user or assistant messages")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM side_threads WHERE thread_id = ?", (thread_id,)).fetchone()
            if row is None:
                connection.rollback()
                return None
            now = _now()
            self._append_event(
                connection,
                thread_id,
                f"{role}_message",
                {"content": content, "attachments": attachments or []},
                created_at=now,
            )
            connection.execute(
                "UPDATE side_threads SET version = version + 1, updated_at = ? WHERE thread_id = ?",
                (now, thread_id),
            )
            updated = connection.execute("SELECT * FROM side_threads WHERE thread_id = ?", (thread_id,)).fetchone()
            messages = self._messages(connection, thread_id)
            connection.commit()
        return self._thread_from_row(updated, messages=messages)

    def complete_turn(
        self,
        *,
        thread_id: str,
        user_content: str,
        attachments: list[dict[str, Any]],
        answer: str,
        artifact_key: str,
        artifact_state: dict[str, Any],
        expected_artifact_revision: int,
        next_status: str = "waiting_user",
    ) -> dict[str, Any]:
        if next_status not in {"waiting_user", "waiting_confirmation", "completed", "failed"}:
            raise ThreadStoreError(f"invalid turn completion status: {next_status}")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            thread = connection.execute("SELECT * FROM side_threads WHERE thread_id = ?", (thread_id,)).fetchone()
            if thread is None:
                connection.rollback()
                raise ThreadStoreError("side thread not found")
            if thread["status"] != "active":
                connection.rollback()
                raise ThreadStoreError("side thread has no active turn")

            artifact = connection.execute(
                "SELECT state, revision FROM workflow_artifacts WHERE parent_session_id = ? AND artifact_key = ?",
                (thread["parent_session_id"], artifact_key),
            ).fetchone()
            current_revision = int(artifact["revision"]) if artifact else 0
            current_state = _load(artifact["state"], {}) if artifact else {}
            if current_revision != expected_artifact_revision:
                connection.rollback()
                raise WorkflowConflictError("workflow state changed while the side thread was running")

            now = _now()
            self._append_event(
                connection, thread_id, "user_message", {"content": user_content, "attachments": attachments}, created_at=now
            )
            if artifact_state != current_state:
                next_revision = current_revision + 1
                connection.execute(
                    """
                    INSERT INTO workflow_artifacts(parent_session_id, artifact_key, state, revision, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(parent_session_id, artifact_key) DO UPDATE SET
                        state = excluded.state, revision = excluded.revision, updated_at = excluded.updated_at
                    """,
                    (thread["parent_session_id"], artifact_key, _json(artifact_state), next_revision, now),
                )
                self._append_event(
                    connection,
                    thread_id,
                    "workflow_handoff",
                    {"artifact_key": artifact_key, "revision": next_revision},
                    created_at=now,
                )
            self._append_event(connection, thread_id, "assistant_message", {"content": answer}, created_at=now)
            checkpoint_ref = f"event:{self._append_event(connection, thread_id, 'checkpoint', {'status': next_status}, created_at=now)}"
            connection.execute(
                """
                UPDATE side_threads
                SET status = ?, checkpoint_ref = ?, version = version + 1, updated_at = ?
                WHERE thread_id = ?
                """,
                (next_status, checkpoint_ref, now, thread_id),
            )
            self._append_event(
                connection, thread_id, "status_changed", {"from": "active", "to": next_status}, created_at=now
            )
            updated = connection.execute("SELECT * FROM side_threads WHERE thread_id = ?", (thread_id,)).fetchone()
            messages = self._messages(connection, thread_id)
            connection.commit()
        return self._thread_from_row(updated, messages=messages)

    def set_workflow_state(self, parent_session_id: str, artifact_key: str, state: dict[str, Any] | None) -> int:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT revision FROM workflow_artifacts WHERE parent_session_id = ? AND artifact_key = ?",
                (parent_session_id, artifact_key),
            ).fetchone()
            revision = int(row["revision"]) if row else 0
            if state is None:
                connection.execute(
                    "DELETE FROM workflow_artifacts WHERE parent_session_id = ? AND artifact_key = ?",
                    (parent_session_id, artifact_key),
                )
                connection.commit()
                return revision + 1
            next_revision = revision + 1
            connection.execute(
                """
                INSERT INTO workflow_artifacts(parent_session_id, artifact_key, state, revision, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(parent_session_id, artifact_key) DO UPDATE SET
                    state = excluded.state, revision = excluded.revision, updated_at = excluded.updated_at
                """,
                (parent_session_id, artifact_key, _json(state), next_revision, _now()),
            )
            connection.commit()
            return next_revision

    def get_workflow_state(self, parent_session_id: str, artifact_key: str) -> tuple[dict[str, Any] | None, int]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT state, revision FROM workflow_artifacts WHERE parent_session_id = ? AND artifact_key = ?",
                (parent_session_id, artifact_key),
            ).fetchone()
            if row is None:
                return None, 0
            return _load(row["state"], {}), int(row["revision"])

    def import_workflow_state(self, parent_session_id: str, artifact_key: str, state: dict[str, Any]) -> None:
        existing, _ = self.get_workflow_state(parent_session_id, artifact_key)
        if existing is None:
            self.set_workflow_state(parent_session_id, artifact_key, state)

    def transition(self, thread_id: str, target_status: str) -> dict[str, Any] | None:
        if target_status not in THREAD_STATUSES:
            raise ThreadStoreError(f"unsupported thread status: {target_status}")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM side_threads WHERE thread_id = ?", (thread_id,)).fetchone()
            if row is None:
                connection.rollback()
                return None
            source = row["status"]
            if target_status not in _ALLOWED_TRANSITIONS.get(source, set()):
                connection.rollback()
                raise ThreadStoreError(f"invalid side thread status transition: {source} -> {target_status}")
            now = _now()
            connection.execute(
                "UPDATE side_threads SET status = ?, version = version + 1, updated_at = ? WHERE thread_id = ?",
                (target_status, now, thread_id),
            )
            self._append_event(connection, thread_id, "status_changed", {"from": source, "to": target_status}, created_at=now)
            updated = connection.execute("SELECT * FROM side_threads WHERE thread_id = ?", (thread_id,)).fetchone()
            messages = self._messages(connection, thread_id)
            connection.commit()
        return self._thread_from_row(updated, messages=messages)

    def fail_turn(self, thread_id: str, reason: str) -> dict[str, Any] | None:
        """Persist a non-sensitive failure event before marking a running turn failed."""
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM side_threads WHERE thread_id = ?", (thread_id,)).fetchone()
            if row is None:
                connection.rollback()
                return None
            if row["status"] != "active":
                connection.rollback()
                raise ThreadStoreError("only an active side thread can fail a turn")
            now = _now()
            self._append_event(connection, thread_id, "turn_failed", {"reason": reason}, created_at=now)
            self._append_event(connection, thread_id, "status_changed", {"from": "active", "to": "failed"}, created_at=now)
            connection.execute(
                "UPDATE side_threads SET status = 'failed', version = version + 1, updated_at = ? WHERE thread_id = ?",
                (now, thread_id),
            )
            updated = connection.execute("SELECT * FROM side_threads WHERE thread_id = ?", (thread_id,)).fetchone()
            messages = self._messages(connection, thread_id)
            connection.commit()
        return self._thread_from_row(updated, messages=messages)

    def delete_parent(self, parent_session_id: str) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM side_threads WHERE parent_session_id = ?", (parent_session_id,))
            connection.execute("DELETE FROM workflow_artifacts WHERE parent_session_id = ?", (parent_session_id,))
            connection.commit()
