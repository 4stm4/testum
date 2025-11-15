# SPDX-License-Identifier: MIT
"""Taskiq broker and scheduler configuration."""
from taskiq import TaskiqScheduler
from taskiq_postgres import PostgresAsyncResultBackend, PostgresBroker
from app.config import config

# Create result backend using Postgres
result_backend = PostgresAsyncResultBackend(dsn=config.DATABASE_URL)

# Create broker with result backend
broker = PostgresBroker(
    dsn=config.DATABASE_URL,
    result_backend=result_backend,
)

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
