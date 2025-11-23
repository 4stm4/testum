"""Единая инициализация очереди задач pyjobkit."""

from app.config import config
from app.tasks_new import DeployKeysExecutor, RunCommandExecutor
from pyjobkit import Engine
from pyjobkit.backends.sql import SQLBackend
from sqlalchemy.ext.asyncio import create_async_engine


DATABASE_URL = config.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
async_engine = create_async_engine(DATABASE_URL)
backend = SQLBackend(async_engine)
engine = Engine(backend=backend, executors=[DeployKeysExecutor(), RunCommandExecutor()])

__all__ = ["engine"]
