"""Task queue engine — composition root that wires adapters into PyJobKit."""
from __future__ import annotations

from pyjobkit import Engine

from adapters.notifications.smtp_webhook import SmtpWebhookNotifier
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
    executors = [
        DeployKeysExecutor(storage=storage, artifact_store=artifacts),
        RunCommandExecutor(storage=storage, artifact_store=artifacts, notifier=notifier),
    ]
    return Engine(backend=_make_backend(), executors=executors)


engine = _build_engine()
backend = engine.backend  # exposed for scheduler/admin use

__all__ = ["backend", "engine"]
