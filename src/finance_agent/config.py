from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_dotenv(path: Path | None = None) -> None:
    env_path = path or PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    lmstudio_base_url: str
    lmstudio_model: str
    lmstudio_api_key: str
    lmstudio_timeout_seconds: int
    result_narration_timeout_seconds: int
    executor_mode: str
    database_url: str
    db_statement_timeout_ms: int
    db_max_rows: int
    catalog_path: Path
    policy_path: Path
    operations_path: Path
    skills_path: Path
    audit_log_path: Path
    private_result_store_path: Path
    public_memory_path: Path
    run_store_path: Path
    kyc_draft_path: Path
    session_store_path: Path
    auth_mode: str
    auth_secret: str
    # PostgreSQL 配置
    pg_host: str
    pg_port: str
    pg_database: str
    pg_user: str
    pg_password: str


def get_settings() -> Settings:
    load_dotenv()
    return Settings(
        lmstudio_base_url=os.environ.get("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1").rstrip("/"),
        lmstudio_model=os.environ.get("LMSTUDIO_MODEL", "qwen2.5-coder-7b-instruct-mlx"),
        lmstudio_api_key=os.environ.get("LMSTUDIO_API_KEY", "lm-studio"),
        lmstudio_timeout_seconds=int(os.environ.get("LMSTUDIO_TIMEOUT_SECONDS", "30")),
        result_narration_timeout_seconds=int(os.environ.get("RESULT_NARRATION_TIMEOUT_SECONDS", "8")),
        executor_mode=os.environ.get("EXECUTOR_MODE", "mock"),
        database_url=os.environ.get("DATABASE_URL", ""),
        db_statement_timeout_ms=int(os.environ.get("DB_STATEMENT_TIMEOUT_MS", "30000")),
        db_max_rows=int(os.environ.get("DB_MAX_ROWS", "1000")),
        catalog_path=Path(os.environ.get("CATALOG_PATH", str(PROJECT_ROOT / "config" / "catalog.yaml"))),
        policy_path=Path(os.environ.get("POLICY_PATH", str(PROJECT_ROOT / "config" / "policy.yaml"))),
        operations_path=Path(os.environ.get("OPERATIONS_PATH", str(PROJECT_ROOT / "config" / "operations.yaml"))),
        skills_path=Path(os.environ.get("SKILLS_PATH", str(PROJECT_ROOT / "config" / "skills.yaml"))),
        audit_log_path=Path(os.environ.get("AUDIT_LOG_PATH", str(PROJECT_ROOT / "data" / "audit.jsonl"))),
        private_result_store_path=Path(
            os.environ.get("PRIVATE_RESULT_STORE_PATH", str(PROJECT_ROOT / "data" / "private_results.jsonl"))
        ),
        public_memory_path=Path(os.environ.get("PUBLIC_MEMORY_PATH", str(PROJECT_ROOT / "data" / "public_memory.jsonl"))),
        run_store_path=Path(os.environ.get("RUN_STORE_PATH", str(PROJECT_ROOT / "data" / "runs.sqlite3"))),
        kyc_draft_path=Path(os.environ.get("KYC_DRAFT_PATH", str(PROJECT_ROOT / "data" / "kyc_drafts"))),
        session_store_path=Path(os.environ.get("SESSION_STORE_PATH", str(PROJECT_ROOT / "data" / "sessions"))),
        auth_mode=os.environ.get("AUTH_MODE", "local").strip().lower(),
        auth_secret=os.environ.get("AUTH_SECRET", ""),
        # PostgreSQL 配置
        pg_host=os.environ.get("PG_HOST", "localhost"),
        pg_port=os.environ.get("PG_PORT", "5432"),
        pg_database=os.environ.get("PG_DATABASE", "finance_sandbox"),
        pg_user=os.environ.get("PG_USER", "postgres"),
        pg_password=os.environ.get("PG_PASSWORD", "postgres"),
    )
