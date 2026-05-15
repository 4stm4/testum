#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/.venv"
REQ="$SCRIPT_DIR/requirements.txt"
HASH_FILE="$VENV/.requirements.hash"

export PYTHONPATH="$SCRIPT_DIR/src"

if [[ ! -d "$VENV" ]]; then
  echo "Creating virtual environment..."
  python3 -m venv "$VENV"
fi

CURRENT_HASH="$(shasum -a 256 "$REQ" | awk '{print $1}')"

if [[ ! -f "$HASH_FILE" ]] || [[ "$CURRENT_HASH" != "$(cat "$HASH_FILE")" ]]; then
  echo "Installing dependencies..."
  "$VENV/bin/pip" install --upgrade pip --quiet
  "$VENV/bin/pip" install --no-cache-dir -r "$REQ" --quiet
  echo "$CURRENT_HASH" > "$HASH_FILE"
  echo "Done."
fi

echo "Starting Testum..."
exec "$VENV/bin/uvicorn" app.main:app --host 0.0.0.0 --port 8000 --reload
