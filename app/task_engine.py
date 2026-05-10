"""Единая инициализация очереди задач pyjobkit."""

from app.config import config
from app.tasks_new import DeployKeysExecutor, RunCommandExecutor
from pyjobkit import Engine
from pyjobkit.backends.sql import SQLBackend
from sqlalchemy.ext.asyncio import create_async_engine


def _make_async_url(url: str) -> str:
    return url.replace("postgresql://", "postgresql+asyncpg://", 1)


if config.APP_ENV == "testing" or config.DATABASE_URL.startswith("sqlite"):
    # In test environments use an in-memory/stub backend so that importing
    # this module does not require a live async-capable database driver.
    from pyjobkit.backends.memory import MemoryBackend
    backend = MemoryBackend()
else:
    DATABASE_URL = _make_async_url(config.DATABASE_URL)
    async_engine = create_async_engine(DATABASE_URL)
    backend = SQLBackend(async_engine)

engine = Engine(backend=backend, executors=[DeployKeysExecutor(), RunCommandExecutor()])

__all__ = ["backend", "engine"]
