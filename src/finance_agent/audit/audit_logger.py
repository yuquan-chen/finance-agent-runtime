from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any


def stable_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class AuditLogger:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: dict[str, Any]) -> dict[str, Any]:
        enriched = {
            "audit_ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            **event,
        }
        enriched["event_hash"] = stable_hash(enriched)
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(enriched, ensure_ascii=False, default=str) + "\n")
        return enriched
