#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/.venv"
REQ="$SCRIPT_DIR/requirements.txt"
HASH_FILE="$VENV/.requirements.hash"
ENV_FILE="$SCRIPT_DIR/.env"

export PYTHONPATH="$SCRIPT_DIR/src"

# ── Virtual environment ────────────────────────────────────────────────────

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

# ── .env defaults (created once, never overwritten) ───────────────────────

if [[ ! -f "$ENV_FILE" ]]; then
  FERNET_KEY="$("$VENV/bin/python" -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
  cat > "$ENV_FILE" <<EOF
# Local development defaults — edit freely, never committed to git
DATABASE_URL=sqlite:///$SCRIPT_DIR/dev.db
FERNET_KEY=$FERNET_KEY
SECRET_KEY=dev-secret-key
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
APP_ENV=development
SSH_HOST_KEY_POLICY=auto_add
# MinIO is optional for local dev — artifact uploads will be skipped if unavailable
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
EOF
  echo "Created .env with generated FERNET_KEY and SQLite database."
fi

# Load .env into the current shell
set -o allexport
# shellcheck disable=SC1090
source "$ENV_FILE"
set +o allexport

# ── Database migrations ────────────────────────────────────────────────────

echo "Running migrations..."
"$VENV/bin/alembic" upgrade head

# ── Start ─────────────────────────────────────────────────────────────────

echo "Starting Testum on http://localhost:8000 (admin / ${ADMIN_PASSWORD:-admin123})"
exec "$VENV/bin/uvicorn" app.main:app --host 0.0.0.0 --port 8000 --reload
