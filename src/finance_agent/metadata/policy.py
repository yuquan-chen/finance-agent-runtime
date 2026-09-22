from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class ApprovalPolicy(BaseModel):
    auto_execute_intents: list[str] = Field(default_factory=list)
    require_approval_for_opencode: bool = True


class Policy(BaseModel):
    version: str
    max_rows: int = 1000
    statement_timeout_ms: int = 30000
    default_limit: int = 50
    planner_max_retries: int = 2
    sensitive_column_patterns: list[str] = Field(default_factory=list)
    forbidden_sql_keywords: list[str] = Field(default_factory=list)
    approval: ApprovalPolicy = Field(default_factory=ApprovalPolicy)

    def is_sensitive_column_name(self, name: str) -> bool:
        lowered = name.lower()
        return any(re.search(pattern, lowered, re.IGNORECASE) for pattern in self.sensitive_column_patterns)


def load_policy(path: Path) -> Policy:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return Policy.model_validate(raw)
