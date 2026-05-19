# SPDX-License-Identifier: MIT
"""Application configuration loaded from environment variables."""
import os
from typing import Optional


class Config:
    """Application configuration."""

    # Application
    APP_ENV: str = os.getenv("APP_ENV", "development")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production")
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin123")

    # Encryption - REQUIRED
    FERNET_KEY: Optional[str] = os.getenv("FERNET_KEY")

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/ocultum"
    )

    # MinIO S3
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    MINIO_BUCKET: str = os.getenv("MINIO_BUCKET", "ocultum-artifacts")
    MINIO_SECURE: bool = os.getenv("MINIO_SECURE", "false").lower() == "true"

    # SSH
    SSH_HOST_KEY_POLICY: str = os.getenv("SSH_HOST_KEY_POLICY", "auto_add")

    # SMTP (optional — used for email notifications)
    SMTP_HOST: Optional[str] = os.getenv("SMTP_HOST")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: Optional[str] = os.getenv("SMTP_USER")
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD")
    SMTP_FROM: str = os.getenv("SMTP_FROM", "testum@localhost")
    SMTP_TLS: bool = os.getenv("SMTP_TLS", "true").lower() == "true"

    # Nervum SDN
    NERVUM_URL: Optional[str] = os.getenv("NERVUM_URL")           # e.g. http://nervum:8080
    NERVUM_TOKEN: Optional[str] = os.getenv("NERVUM_TOKEN")       # service account token
    NERVUM_WEBHOOK_SECRET: Optional[str] = os.getenv("NERVUM_WEBHOOK_SECRET")  # HMAC secret (from nervum at sub creation)
    NERVUM_WEBHOOK_PATH: str = os.getenv("NERVUM_WEBHOOK_PATH", "/webhooks/nervum")
    NERVUM_CALLBACK_URL: Optional[str] = os.getenv("NERVUM_CALLBACK_URL")   # e.g. https://testum.example.com/webhooks/nervum
    NERVUM_SA_NAME: str = os.getenv("NERVUM_SA_NAME", "testum-sync")

    @classmethod
    def validate(cls):
        """Validate required configuration values."""
        if not cls.FERNET_KEY:
            raise ValueError(
                "FERNET_KEY environment variable is required. "
                "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )


# Validate config on import
Config.validate()

config = Config()
