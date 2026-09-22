#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

if [ -x .venv/bin/python ]; then
  PY=.venv/bin/python
else
  PY="${PYTHON:-python3}"
fi

EXECUTOR_MODE_VALUE="${EXECUTOR_MODE:-mock}"
SCHEMA_PATH="${SCHEMA_CATALOG_PATH:-schema_catalog/schema.yaml}"
if [ ! -f "$SCHEMA_PATH" ]; then
  if [ "$EXECUTOR_MODE_VALUE" = "mock" ] && [ -f "schema_catalog/demo_schema.yaml" ]; then
    echo "Schema snapshot not found; using bundled demo schema for mock mode"
    export SCHEMA_CATALOG_PATH="schema_catalog/demo_schema.yaml"
  elif [ -n "${DATABASE_URL:-}" ]; then
    echo "Schema snapshot not found; extracting database metadata to $SCHEMA_PATH"
    "$PY" scripts/extract_schema.py --from-db "$DATABASE_URL" --output "$SCHEMA_PATH"
  else
    echo "Schema snapshot not found: $SCHEMA_PATH"
    echo "Set DATABASE_URL and restart, or generate it with:"
    echo "  $PY scripts/extract_schema.py --from-db <DATABASE_URL> --output $SCHEMA_PATH"
    exit 1
  fi
fi

HOST="${APP_HOST:-127.0.0.1}"
PORT="${APP_PORT:-8810}"

exec "$PY" -m uvicorn finance_agent.api.app:app --host "$HOST" --port "$PORT" --reload
