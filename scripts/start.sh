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

HOST="${APP_HOST:-127.0.0.1}"
PORT="${APP_PORT:-8810}"

exec "$PY" -m uvicorn finance_agent.api.app:app --host "$HOST" --port "$PORT" --reload
