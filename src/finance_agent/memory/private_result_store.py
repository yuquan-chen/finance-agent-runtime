from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from finance_agent.audit.audit_logger import stable_hash


class PrivateResultRecord(BaseModel):
    result_ref: str
    request_id: str
    method_name: str
    method_hash: str
    authorization_hash: str
    result: dict[str, Any] | list[dict[str, Any]]
    row_count: int
    result_hash: str
    created_at: str
    visible_to_llm: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class PrivateResultStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(
        self,
        *,
        request_id: str,
        method_name: str,
        method_hash: str,
        authorization_hash: str,
        result: dict[str, Any] | list[dict[str, Any]],
        row_count: int,
        metadata: dict[str, Any] | None = None,
    ) -> PrivateResultRecord:
        record = PrivateResultRecord(
            result_ref=f"result_{uuid.uuid4().hex}",
            request_id=request_id,
            method_name=method_name,
            method_hash=method_hash,
            authorization_hash=authorization_hash,
            result=result,
            row_count=row_count,
            result_hash=stable_hash(result),
            created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            metadata=metadata or {},
        )
        with self.path.open("a", encoding="utf-8") as file:
            file.write(record.model_dump_json() + "\n")
        return record

    def latest(self, limit: int = 5) -> list[PrivateResultRecord]:
        if not self.path.exists():
            return []
        lines = [line for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
        records = [PrivateResultRecord.model_validate(json.loads(line)) for line in lines[-limit:]]
        return list(reversed(records))
