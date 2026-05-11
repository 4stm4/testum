# SPDX-License-Identifier: MIT
"""MinIO/S3 artifact store."""
from __future__ import annotations

import logging

import boto3
from botocore.client import Config

from app.config import config

logger = logging.getLogger(__name__)


class MinioArtifactStore:
    def __init__(self) -> None:
        scheme = "https" if config.MINIO_SECURE else "http"
        self._client = boto3.client(
            "s3",
            endpoint_url=f"{scheme}://{config.MINIO_ENDPOINT}",
            aws_access_key_id=config.MINIO_ACCESS_KEY,
            aws_secret_access_key=config.MINIO_SECRET_KEY,
            config=Config(signature_version="s3v4"),
        )
        self._bucket = config.MINIO_BUCKET

    def _ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except Exception:
            logger.info("Creating bucket: %s", self._bucket)
            self._client.create_bucket(Bucket=self._bucket)

    def upload(self, key: str, content: str) -> str:
        self._ensure_bucket()
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=content.encode("utf-8"),
            ContentType="text/plain",
        )
        logger.info("Uploaded to S3: %s", key)
        return key

    def download(self, key: str) -> str:
        obj = self._client.get_object(Bucket=self._bucket, Key=key)
        return obj["Body"].read().decode("utf-8")
