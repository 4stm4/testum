#!/bin/bash
set -e

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
