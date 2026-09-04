from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@dataclass(frozen=True)
class ActionClaim:
    status: str
    state: dict[str, Any] | None = None


RUN_TERMINAL_STATUSES = frozenset({
    "executed_simulated_real",
    "executed",
    "method_execution_failed",
    "method_generation_failed",
    "method_review_failed",
    "method_repair_failed",
    "method_refused",
    "refused",
    "clarification",
    "skill_card_ready",
    "prior_result_not_found",
    "dependent_method_failed",
})


class RunStore:
    """Durable run snapshots and idempotent command receipts.

    The store contains safe run state only. Raw query rows remain in
    ``PrivateResultStore`` and are never copied into this control-plane DB.
    """

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    request_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    state_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_runs_owner
                    ON runs(workspace_id, user_id, updated_at DESC);

                CREATE TABLE IF NOT EXISTS run_actions (
                    request_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    status TEXT NOT NULL,
                    response_json TEXT,
                    started_at TEXT NOT NULL,
                    lease_until REAL,
                    attempts INTEGER NOT NULL DEFAULT 1,
                    completed_at TEXT,
                    PRIMARY KEY(request_id, action, idempotency_key),
                    FOREIGN KEY(request_id) REFERENCES runs(request_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_run_actions_status
                    ON run_actions(request_id, action, status);

                CREATE TABLE IF NOT EXISTS run_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    from_status TEXT,
                    to_status TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(request_id) REFERENCES runs(request_id) ON DELETE CASCADE
                );
                """
            )
            self._ensure_column(connection, "run_actions", "lease_until", "REAL")
            self._ensure_column(connection, "run_actions", "attempts", "INTEGER NOT NULL DEFAULT 1")

    @staticmethod
    def _ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    @staticmethod
    def _safe_payload(value: Any) -> Any:
        """Keep control-plane snapshots free of raw result rows and private text."""
        excluded = {
            "result", "rows", "referenced_result_data",
            "result_narration", "result_narrations",
            "execution_result_card", "execution_result_cards",
            "mock_result", "mock_results",
            "private_analysis", "public_memory_entry", "public_memory_entries",
        }
        if isinstance(value, dict):
            return {
                key: RunStore._safe_payload(item)
                for key, item in value.items()
                if key not in excluded
            }
        if isinstance(value, list):
            return [RunStore._safe_payload(item) for item in value]
        return value

    @staticmethod
    def _state(row: sqlite3.Row, column: str = "state_json") -> dict[str, Any]:
        value = json.loads(row[column])
        return value if isinstance(value, dict) else {}

    def save(self, state: dict[str, Any], payload: dict[str, Any]) -> None:
        request_id = str(state.get("request_id") or "")
        session_id = str(state.get("session_id") or "")
        user_id = str(state.get("user_id") or "local")
        workspace_id = str(state.get("workspace_id") or "local")
        if not request_id or not session_id:
            return
        now = _now()
        encoded = json.dumps(self._safe_payload(payload), ensure_ascii=False, separators=(",", ":"), default=str)
        with self._connect() as connection:
            current = connection.execute(
                "SELECT status, user_id, workspace_id FROM runs WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            if current and (
                str(current["user_id"]) != user_id
                or str(current["workspace_id"]) != workspace_id
            ):
                return
            current_status = str(current["status"]) if current else None
            next_status = str(state.get("status") or "unknown")
            if current_status in RUN_TERMINAL_STATUSES and next_status != current_status:
                return
            saved = connection.execute(
                """
                INSERT INTO runs(request_id, session_id, user_id, workspace_id, status, version, state_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
                ON CONFLICT(request_id) DO UPDATE SET
                    session_id = excluded.session_id,
                    user_id = excluded.user_id,
                    workspace_id = excluded.workspace_id,
                    status = excluded.status,
                    version = runs.version + 1,
                    state_json = excluded.state_json,
                    updated_at = excluded.updated_at
                WHERE runs.user_id = excluded.user_id
                  AND runs.workspace_id = excluded.workspace_id
                """,
                (request_id, session_id, user_id, workspace_id, str(state.get("status") or "unknown"), encoded, now, now),
            )
            if saved.rowcount == 1:
                updated = connection.execute(
                    "SELECT version FROM runs WHERE request_id = ?",
                    (request_id,),
                ).fetchone()
                if current_status != next_status:
                    connection.execute(
                        "INSERT INTO run_events(request_id, from_status, to_status, version, created_at) VALUES (?, ?, ?, ?, ?)",
                        (request_id, current_status, next_status, int(updated["version"]), now),
                    )

    def get(self, request_id: str, *, user_id: str, workspace_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT state_json FROM runs WHERE request_id = ? AND user_id = ? AND workspace_id = ?",
                (request_id, user_id, workspace_id),
            ).fetchone()
        return self._state(row) if row else None

    def claim_action(
        self,
        request_id: str,
        *,
        action: str,
        idempotency_key: str,
        user_id: str,
        workspace_id: str,
        lease_seconds: int = 300,
    ) -> ActionClaim:
        """Atomically claim an approval/revision command for one run."""
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            run = connection.execute(
                "SELECT request_id FROM runs WHERE request_id = ? AND user_id = ? AND workspace_id = ?",
                (request_id, user_id, workspace_id),
            ).fetchone()
            if run is None:
                connection.rollback()
                return ActionClaim("not_found")

            existing = connection.execute(
                """
                SELECT status, response_json, lease_until FROM run_actions
                WHERE request_id = ? AND action = ? AND idempotency_key = ?
                """,
                (request_id, action, idempotency_key),
            ).fetchone()
            if existing:
                if existing["status"] == "completed" and existing["response_json"]:
                    return ActionClaim("completed", json.loads(existing["response_json"]))
                expired = (
                    existing["status"] == "in_progress"
                    and (existing["lease_until"] is None or float(existing["lease_until"]) <= time.time())
                )
                if existing["status"] == "failed" or expired:
                    connection.execute(
                        """
                        UPDATE run_actions
                        SET status = 'in_progress', lease_until = ?, attempts = attempts + 1,
                            started_at = ?, completed_at = NULL
                        WHERE request_id = ? AND action = ? AND idempotency_key = ?
                        """,
                        (time.time() + max(1, lease_seconds), _now(), request_id, action, idempotency_key),
                    )
                    return ActionClaim("claimed")
                return ActionClaim("in_progress")

            connection.execute(
                """
                INSERT INTO run_actions(request_id, action, idempotency_key, status, started_at, lease_until)
                VALUES (?, ?, ?, 'in_progress', ?, ?)
                """,
                (request_id, action, idempotency_key, _now(), time.time() + max(1, lease_seconds)),
            )
            return ActionClaim("claimed")

    def complete_action(
        self,
        request_id: str,
        *,
        action: str,
        idempotency_key: str,
        state: dict[str, Any],
        payload: dict[str, Any],
    ) -> None:
        now = _now()
        encoded_state = json.dumps(self._safe_payload(state), ensure_ascii=False, separators=(",", ":"), default=str)
        encoded_response = json.dumps(self._safe_payload(payload), ensure_ascii=False, separators=(",", ":"), default=str)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT status, version FROM runs WHERE request_id = ? AND user_id = ? AND workspace_id = ?",
                (
                    request_id,
                    str(state.get("user_id") or "local"),
                    str(state.get("workspace_id") or "local"),
                ),
            ).fetchone()
            completed = connection.execute(
                "UPDATE run_actions SET status = 'completed', response_json = ?, lease_until = NULL, completed_at = ? WHERE request_id = ? AND action = ? AND idempotency_key = ? AND status = 'in_progress'",
                (encoded_response, now, request_id, action, idempotency_key),
            )
            if completed.rowcount != 1 or current is None:
                connection.rollback()
                return
            updated = connection.execute(
                """
                UPDATE runs
                SET status = ?, version = version + 1, state_json = ?, updated_at = ?
                WHERE request_id = ? AND user_id = ? AND workspace_id = ?
                """,
                (
                    str(state.get("status") or "unknown"),
                    encoded_state,
                    now,
                    request_id,
                    str(state.get("user_id") or "local"),
                    str(state.get("workspace_id") or "local"),
                ),
            )
            if updated.rowcount == 1:
                connection.execute(
                    "INSERT INTO run_events(request_id, from_status, to_status, version, created_at) VALUES (?, ?, ?, ?, ?)",
                    (
                        request_id,
                        str(current["status"]) if current else None,
                        str(state.get("status") or "unknown"),
                        int(current["version"]) + 1 if current else 1,
                        now,
                    ),
                )

    def fail_action(self, request_id: str, *, action: str, idempotency_key: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE run_actions SET status = 'failed', lease_until = NULL, completed_at = ? WHERE request_id = ? AND action = ? AND idempotency_key = ?",
                (_now(), request_id, action, idempotency_key),
            )

    def delete_session(self, session_id: str) -> int:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM runs WHERE session_id = ?", (session_id,))
            return int(cursor.rowcount)

    def renew_action(
        self,
        request_id: str,
        *,
        action: str,
        idempotency_key: str,
        lease_seconds: int = 300,
    ) -> bool:
        """Extend an executing action lease while its worker is alive."""
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE run_actions
                SET lease_until = ?
                WHERE request_id = ? AND action = ? AND idempotency_key = ?
                  AND status = 'in_progress'
                """,
                (time.time() + max(1, lease_seconds), request_id, action, idempotency_key),
            )
            return cursor.rowcount == 1

    def list_events(self, request_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT from_status, to_status, version, created_at
                FROM run_events WHERE request_id = ? ORDER BY event_id
                """,
                (request_id,),
            ).fetchall()
        return [dict(row) for row in rows]
