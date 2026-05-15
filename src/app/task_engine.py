"""Task queue engine — composition root that wires adapters into PyJobKit."""
from __future__ import annotations

import os

from pyjobkit import Engine
from pyjobkit.retry import JitteredExponentialBackoff, parse_policy

from adapters.notifications.smtp_webhook import SmtpWebhookNotifier
from adapters.postgres.log_sink import TaskRunLogSink
from adapters.postgres.storage import SQLStorage
from adapters.queue.pyjobkit import DeployKeysExecutor, RunCommandExecutor
from adapters.storage.minio import MinioArtifactStore
from app.config import config


_LEASE_TTL = int(os.getenv("WORKER_LEASE_TTL", "60"))

# Default: jittered exponential, 1s → 2s → 4s … capped at 5 min, ±20 % spread.
# Override via WORKER_RETRY_POLICY, e.g. "fixed:5" or "exponential:2:3:120".
_DEFAULT_RETRY_POLICY = JitteredExponentialBackoff(
    base=1.0, factor=2.0, max_delay_s=300.0, jitter=0.2
)


def _make_backend():
    if config.DATABASE_URL.startswith("sqlite"):
        from pyjobkit.backends.memory import MemoryBackend
        return MemoryBackend(lease_ttl_s=_LEASE_TTL)
    from pyjobkit.backends.sql import SQLBackend
    from sqlalchemy.ext.asyncio import create_async_engine
    url = config.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    return SQLBackend(create_async_engine(url), lease_ttl_s=_LEASE_TTL)


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
    stop_timeout = float(os.getenv("WORKER_STOP_TIMEOUT", "120.0"))
    watchdog_interval_s = float(os.getenv("WORKER_WATCHDOG_INTERVAL", "15.0"))

    retry_policy_spec = os.getenv("WORKER_RETRY_POLICY")
    retry_policy = parse_policy(retry_policy_spec) if retry_policy_spec else _DEFAULT_RETRY_POLICY

    return Worker(
        engine,
        max_concurrency=max_concurrency,
        lease_ttl=_LEASE_TTL,
        stop_timeout=stop_timeout,
        retry_policy=retry_policy,
        watchdog_interval_s=watchdog_interval_s,
    )


__all__ = ["backend", "engine", "worker_factory"]
