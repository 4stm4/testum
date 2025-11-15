# SPDX-License-Identifier: MIT
"""Taskiq broker and scheduler configuration."""
from taskiq import TaskiqScheduler
from taskiq_pg.asyncpg import AsyncpgBroker, AsyncpgResultBackend
from app.config import config

# Create result backend using Postgres
result_backend = AsyncpgResultBackend(dsn=config.DATABASE_URL)

# Create broker with result backend
broker = AsyncpgBroker(dsn=config.DATABASE_URL).with_result_backend(result_backend)

# Optional: Create scheduler for periodic tasks
scheduler = TaskiqScheduler(broker=broker)

# Task decorator
task = broker.task


async def startup():
    """Initialize broker on startup."""
    await broker.startup()


async def shutdown():
    """Cleanup broker on shutdown."""
    await broker.shutdown()
