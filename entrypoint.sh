#!/bin/bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ensure_python_module() {
  local module_name="$1"
  local package_spec="${2:-$1}"

  if ! python -c "import importlib, sys; importlib.import_module(sys.argv[1])" "${module_name}" >/dev/null 2>&1; then
    if command -v python >/dev/null 2>&1 && python -m pip --version >/dev/null 2>&1; then
      echo "Python module '$module_name' not found. Installing $package_spec..."
      python -m pip install --no-cache-dir "$package_spec"
    else
      echo "Python module '$module_name' is missing and pip is unavailable to install $package_spec" >&2
      exit 1
    fi
  fi
}

if [[ "${USE_RUNTIME_INSTALL:-0}" == "1" ]]; then
  RUNTIME_CACHE_DIR="${RUNTIME_CACHE_DIR:-/runtime-cache}"
  VENV_PATH="${VENV_PATH:-$RUNTIME_CACHE_DIR/venv}"
  LOCK_FILE="$RUNTIME_CACHE_DIR/runtime.lock"
  REQUIREMENTS_FILE="$APP_DIR/requirements.txt"

  mkdir -p "$RUNTIME_CACHE_DIR"

  (
    flock 9

    if ! command -v pg_isready >/dev/null 2>&1; then
      echo "Installing system dependencies..."
      apt-get update
      apt-get install -y --no-install-recommends postgresql-client
      rm -rf /var/lib/apt/lists/*
    fi

    CURRENT_HASH="$(sha256sum "$REQUIREMENTS_FILE" | awk '{print $1}')"
    HASH_FILE="$RUNTIME_CACHE_DIR/requirements.hash"

    if [ ! -d "$VENV_PATH" ] || [ ! -f "$HASH_FILE" ] || [ "$CURRENT_HASH" != "$(cat "$HASH_FILE")" ]; then
      echo "Preparing Python virtual environment..."
      rm -rf "$VENV_PATH"
      python -m venv "$VENV_PATH"
      # shellcheck disable=SC1091
      source "$VENV_PATH/bin/activate"
      pip install --upgrade pip
      pip install --no-cache-dir -r "$REQUIREMENTS_FILE"
      echo "$CURRENT_HASH" > "$HASH_FILE"
    fi
  ) 9>"$LOCK_FILE"

  if [ -d "$VENV_PATH" ]; then
    # shellcheck disable=SC1091
    source "$VENV_PATH/bin/activate"
  else
    echo "Virtual environment not found at $VENV_PATH" >&2
    exit 1
  fi

  ensure_python_module "uvicorn" "uvicorn[standard]==0.32.1"
  ensure_python_module "taskiq" "taskiq==0.11.7"
fi

ensure_python_module "uvicorn" "uvicorn[standard]==0.32.1"
ensure_python_module "taskiq" "taskiq==0.11.7"

if [ -z "${FERNET_KEY:-}" ]; then
  echo "FERNET_KEY environment variable is required"
  exit 1
fi

echo "Waiting for database..."
until pg_isready -h db -p 5432 -U postgres; do
  echo "Database is unavailable - sleeping"
  sleep 2
done

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  echo "Database is up - running migrations"
  alembic upgrade head
else
  echo "Database is up - skipping migrations (RUN_MIGRATIONS=${RUN_MIGRATIONS})"
fi

echo "Starting application..."
exec "$@"
