#!/bin/sh
# pg_dump → gzip → upload to MinIO
# Called by cron inside the backup container.
set -e

: "${DATABASE_URL:?DATABASE_URL is required}"
: "${MINIO_ENDPOINT:?MINIO_ENDPOINT is required}"
: "${MINIO_ACCESS_KEY:?MINIO_ACCESS_KEY is required}"
: "${MINIO_SECRET_KEY:?MINIO_SECRET_KEY is required}"
: "${MINIO_BUCKET:?MINIO_BUCKET is required}"

TIMESTAMP=$(date -u +"%Y%m%d_%H%M%S")
FILENAME="pg_backup_${TIMESTAMP}.sql.gz"
TMP="/tmp/${FILENAME}"

echo "[backup] Starting pg_dump at ${TIMESTAMP}"

pg_dump "${DATABASE_URL}" | gzip > "${TMP}"

echo "[backup] Dump complete ($(du -sh "${TMP}" | cut -f1)), uploading to MinIO…"

python3 /usr/local/bin/backup_runner.py "${TMP}" "${FILENAME}"

rm -f "${TMP}"
echo "[backup] Done — ${FILENAME} uploaded to ${MINIO_BUCKET}/backups/"

# Keep only last 30 backups
python3 - <<'EOF'
import os
from minio import Minio

client = Minio(
    os.environ["MINIO_ENDPOINT"],
    access_key=os.environ["MINIO_ACCESS_KEY"],
    secret_key=os.environ["MINIO_SECRET_KEY"],
    secure=os.environ.get("MINIO_SECURE", "false").lower() == "true",
)
bucket = os.environ["MINIO_BUCKET"]
prefix = "backups/"
objects = sorted(
    client.list_objects(bucket, prefix=prefix),
    key=lambda o: o.object_name,
)
to_delete = objects[:-30] if len(objects) > 30 else []
for obj in to_delete:
    client.remove_object(bucket, obj.object_name)
    print(f"[backup] Pruned old backup: {obj.object_name}")
EOF
