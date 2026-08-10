#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON:-python3}"
PY_VERSION="$($PYTHON_BIN - <<'PY'
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
PY
)"

case "$PY_VERSION" in
  3.11|3.12|3.13) ;;
  *)
    echo "Python 3.11+ is required. Current: $PY_VERSION"
    echo "Try: PYTHON=/path/to/python3.12 ./scripts/setup.sh"
    exit 1
    ;;
esac

"$PYTHON_BIN" -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

echo "Setup complete. Activate with: source .venv/bin/activate"
