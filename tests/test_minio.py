# SPDX-License-Identifier: MIT
"""MinIO integration tests.

Requires a live MinIO instance. Set env vars or uses defaults:
  MINIO_ENDPOINT=192.168.88.199:9000
  MINIO_ACCESS_KEY=testum4a9f2c81b3e7d056
  MINIO_SECRET_KEY=a7f3c9e2b84d1f6a093c5e8b2d4f7a1c9e3b5d7f2a4c6e8
  MINIO_BUCKET=ocultum-artifacts
  MINIO_SECURE=false

Пропускаются автоматически если MinIO недоступен.
"""
from __future__ import annotations

import io
import os
import uuid

import pytest

MINIO_ENDPOINT   = os.getenv("MINIO_ENDPOINT",   "192.168.88.199:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY",  "testum4a9f2c81b3e7d056")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY",  "a7f3c9e2b84d1f6a093c5e8b2d4f7a1c9e3b5d7f2a4c6e8")
MINIO_BUCKET     = os.getenv("MINIO_BUCKET",      "ocultum-artifacts")
MINIO_SECURE     = os.getenv("MINIO_SECURE", "false").lower() == "true"


def _get_client():
    minio = pytest.importorskip("minio", reason="minio SDK not installed")
    return minio.Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE,
    )


@pytest.fixture(scope="module")
def minio_client():
    """Подключаемся к MinIO, пропускаем тесты если недоступен."""
    try:
        client = _get_client()
        # проверяем доступность
        client.list_buckets()
        return client
    except Exception as e:
        pytest.skip(f"MinIO недоступен ({MINIO_ENDPOINT}): {e}")


@pytest.fixture(scope="module")
def bucket(minio_client):
    """Создаём тестовый bucket если не существует, возвращаем имя."""
    if not minio_client.bucket_exists(MINIO_BUCKET):
        minio_client.make_bucket(MINIO_BUCKET)
    return MINIO_BUCKET


# ── connectivity ──────────────────────────────────────────────────────────

def test_minio_connection(minio_client):
    buckets = minio_client.list_buckets()
    assert isinstance(buckets, list)


def test_bucket_exists(minio_client, bucket):
    assert minio_client.bucket_exists(bucket)


# ── put / get / delete ────────────────────────────────────────────────────

def test_upload_and_download(minio_client, bucket):
    key  = f"tests/{uuid.uuid4()}.txt"
    data = b"hello from testum tests"

    minio_client.put_object(bucket, key, io.BytesIO(data), length=len(data),
                             content_type="text/plain")

    response = minio_client.get_object(bucket, key)
    content  = response.read()
    response.close()

    assert content == data

    # cleanup
    minio_client.remove_object(bucket, key)


def test_upload_binary(minio_client, bucket):
    key  = f"tests/{uuid.uuid4()}.bin"
    data = os.urandom(1024)  # 1 KB random

    minio_client.put_object(bucket, key, io.BytesIO(data), length=len(data),
                             content_type="application/octet-stream")

    response = minio_client.get_object(bucket, key)
    content  = response.read()
    response.close()
    assert content == data

    minio_client.remove_object(bucket, key)


def test_list_objects(minio_client, bucket):
    prefix = f"tests/list-{uuid.uuid4()}/"
    keys   = [f"{prefix}file-{i}.txt" for i in range(3)]

    for k in keys:
        minio_client.put_object(bucket, k, io.BytesIO(b"x"), length=1)

    objects = list(minio_client.list_objects(bucket, prefix=prefix))
    names   = [o.object_name for o in objects]
    assert len(names) == 3

    for k in keys:
        minio_client.remove_object(bucket, k)


def test_get_nonexistent_object(minio_client, bucket):
    from minio.error import S3Error
    with pytest.raises(S3Error) as exc_info:
        minio_client.get_object(bucket, f"does-not-exist/{uuid.uuid4()}")
    assert exc_info.value.code in ("NoSuchKey", "NoSuchBucket")


def test_remove_nonexistent_object_ok(minio_client, bucket):
    """Удаление несуществующего объекта не должно бросать исключение."""
    minio_client.remove_object(bucket, f"ghost/{uuid.uuid4()}.bin")


# ── presigned URLs ────────────────────────────────────────────────────────

def test_presigned_get_url(minio_client, bucket):
    from datetime import timedelta
    key  = f"tests/presign-{uuid.uuid4()}.txt"
    data = b"presigned content"

    minio_client.put_object(bucket, key, io.BytesIO(data), length=len(data))

    url = minio_client.presigned_get_object(bucket, key, expires=timedelta(minutes=5))
    assert url.startswith("http")
    assert key in url

    minio_client.remove_object(bucket, key)


# ── large object ─────────────────────────────────────────────────────────

def test_upload_5mb(minio_client, bucket):
    """5 MB upload через multipart (MinIO переключается автоматически)."""
    key  = f"tests/large-{uuid.uuid4()}.bin"
    data = os.urandom(5 * 1024 * 1024)

    minio_client.put_object(bucket, key, io.BytesIO(data), length=len(data))

    response = minio_client.get_object(bucket, key)
    content  = response.read()
    response.close()
    assert len(content) == len(data)

    minio_client.remove_object(bucket, key)
