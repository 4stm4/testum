#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/.venv"

export PYTHONPATH="$SCRIPT_DIR/src"

if [[ ! -d "$VENV" ]]; then
  echo "Creating virtual environment..."
  python3 -m venv "$VENV"
  echo "Installing dependencies..."
  "$VENV/bin/pip" install --upgrade pip --quiet
  "$VENV/bin/pip" install --no-cache-dir -r "$SCRIPT_DIR/requirements.txt" --quiet
  echo "Done."
fi

echo "Starting Testum..."
exec "$VENV/bin/uvicorn" app.main:app --host 0.0.0.0 --port 8000 --reload
