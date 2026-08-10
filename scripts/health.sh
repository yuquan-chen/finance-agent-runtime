#!/usr/bin/env bash
set -euo pipefail

HOST="${APP_HOST:-127.0.0.1}"
PORT="${APP_PORT:-8810}"
curl -sS "http://${HOST}:${PORT}/health"
