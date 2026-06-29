# SPDX-License-Identifier: MIT
"""Application configuration loaded from environment variables."""
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid value for %s=%r, using default %d", name, raw, default)
        return default


class Config:
    """Application configuration."""

    # Application
    APP_ENV: str = os.getenv("APP_ENV", "development")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production")
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin123")

    # JWT
    TOKEN_EXPIRY_HOURS: int = _int_env("TOKEN_EXPIRY_HOURS", 24)

    # CORS — comma-separated origins; "*" only for development
    CORS_ALLOWED_ORIGINS: list[str] = [
        o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "*").split(",") if o.strip()
    ]

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
    SMTP_PORT: int = _int_env("SMTP_PORT", 587)
    SMTP_USER: Optional[str] = os.getenv("SMTP_USER")
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD")
    SMTP_FROM: str = os.getenv("SMTP_FROM", "testum@localhost")
    SMTP_TLS: bool = os.getenv("SMTP_TLS", "true").lower() == "true"

    # Nervum SDN — connection
    NERVUM_URL: Optional[str] = os.getenv("NERVUM_URL")
    NERVUM_WEBHOOK_PATH: str  = os.getenv("NERVUM_WEBHOOK_PATH", "/webhooks/nervum")
    NERVUM_CALLBACK_URL: Optional[str] = os.getenv("NERVUM_CALLBACK_URL")

    # Nervum SDN — T3 service account tokens
    NERVUM_BOOTSTRAP_TOKEN: Optional[str] = os.getenv("NERVUM_BOOTSTRAP_TOKEN")
    NERVUM_TOKEN: Optional[str] = os.getenv("NERVUM_TOKEN")
    NERVUM_WEBHOOK_SECRET: Optional[str] = os.getenv("NERVUM_WEBHOOK_SECRET")
    NERVUM_SA_NAME: str = os.getenv("NERVUM_SA_NAME", "testum-sync")

    @classmethod
    def validate(cls):
        """Validate required configuration values and warn about insecure defaults."""
        if not cls.FERNET_KEY:
            raise ValueError(
                "FERNET_KEY environment variable is required. "
                "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )
        if cls.APP_ENV.lower() == "production":
            if cls.SECRET_KEY == "change-me-in-production":
                raise ValueError("SECRET_KEY must be changed from the default in production.")
            if cls.ADMIN_PASSWORD == "admin123":
                raise ValueError("ADMIN_PASSWORD must be changed from the default in production.")
            if "*" in cls.CORS_ALLOWED_ORIGINS:
                raise ValueError(
                    "CORS_ALLOWED_ORIGINS=* is not allowed in production. "
                    "Set CORS_ALLOWED_ORIGINS to your domain (e.g. https://app.example.com)."
                )
            if cls.SSH_HOST_KEY_POLICY == "auto_add":
                logger.warning(
                    "SSH_HOST_KEY_POLICY=auto_add in production: unknown host keys are accepted "
                    "automatically (TOFU). Set to 'strict' and pre-populate known_hosts for hardened deployments."
                )


# Validate config on import
Config.validate()

config = Config()
