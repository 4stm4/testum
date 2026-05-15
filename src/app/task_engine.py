"""Task queue engine — composition root that wires adapters into PyJobKit."""
from __future__ import annotations

import os

from pyjobkit import Engine

from adapters.notifications.smtp_webhook import SmtpWebhookNotifier
from adapters.postgres.log_sink import TaskRunLogSink
from adapters.postgres.storage import SQLStorage
from adapters.queue.pyjobkit import DeployKeysExecutor, RunCommandExecutor
from adapters.storage.minio import MinioArtifactStore
from app.config import config


def _make_backend():
    if config.DATABASE_URL.startswith("sqlite"):
        from pyjobkit.backends.memory import MemoryBackend
        return MemoryBackend()
    from pyjobkit.backends.sql import SQLBackend
    from sqlalchemy.ext.asyncio import create_async_engine
    url = config.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    return SQLBackend(create_async_engine(url))


def _build_engine() -> Engine:
    storage = SQLStorage()
    artifacts = MinioArtifactStore()
    notifier = SmtpWebhookNotifier(storage)
    log_sink = TaskRunLogSink()
    executors = [
        DeployKeysExecutor(storage=storage, artifact_store=artifacts),
        RunCommandExecutor(storage=storage, artifact_store=artifacts, notifier=notifier),
    ]
    return Engine(backend=_make_backend(), executors=executors, log_sink=log_sink)


engine = _build_engine()
backend = engine.backend  # exposed for scheduler/admin use


def worker_factory():
    """Create a Worker with settings sourced from environment variables."""
    from pyjobkit.worker import Worker

    max_concurrency = int(os.getenv("WORKER_MAX_CONCURRENCY", "4"))
    lease_ttl = int(os.getenv("WORKER_LEASE_TTL", "60"))
    stop_timeout = float(os.getenv("WORKER_STOP_TIMEOUT", "120.0"))

    return Worker(
        engine,
        max_concurrency=max_concurrency,
        lease_ttl=lease_ttl,
        stop_timeout=stop_timeout,
    )


__all__ = ["backend", "engine", "worker_factory"]
