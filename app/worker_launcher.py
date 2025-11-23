"""Reliable entrypoint for starting the pyjobkit worker.

This module adds a small amount of resiliency so the worker can survive
transient database or migration races that often happen when containers
come up together.  It performs an explicit database connectivity check
and retries the worker process a handful of times with backoff before
failing.
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from typing import Optional

import asyncpg


DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_INITIAL_DELAY = 2
DEFAULT_DB_CHECK_ATTEMPTS = 5


def _log(message: str) -> None:
    """Print log messages with a consistent prefix."""
    print(f"[worker-launcher] {message}")


def _database_url() -> str:
    """Resolve the async database URL used by the worker."""
    if db_url := os.getenv("PYJOBKIT_DATABASE_URL"):
        return db_url

    sync_url = os.getenv("DATABASE_URL")
    if not sync_url:
        raise SystemExit(
            "PYJOBKIT_DATABASE_URL or DATABASE_URL must be set for worker startup"
        )

    return sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)


async def _wait_for_db(url: str, attempts: int, delay: int) -> None:
    """Poll the database until a connection succeeds or attempts are exhausted."""
    last_error: Optional[BaseException] = None
    backoff = delay

    for attempt in range(1, attempts + 1):
        try:
            conn = await asyncpg.connect(url)
            await conn.close()
            _log("Database connection established")
            return
        except Exception as exc:  # noqa: BLE001 - surface real startup failures
            last_error = exc
            _log(
                f"Database connection failed on attempt {attempt}/{attempts}: {exc}"
            )
            if attempt < attempts:
                _log(f"Retrying database check in {backoff}s...")
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)

    raise SystemExit(f"Unable to connect to database: {last_error}")


def _run_worker(engine: str, db_url: str, attempts: int, delay: int) -> int:
    """Spawn the pyjobkit worker with retry/backoff."""
    command = [sys.executable, "-m", "pyjobkit.worker", "--engine", engine]
    if db_url:
        command.extend(["--database-url", db_url])

    backoff = delay
    for attempt in range(1, attempts + 1):
        _log(
            f"Starting worker (attempt {attempt}/{attempts})... command={' '.join(command)}"
        )
        result = subprocess.run(command, check=False)
        if result.returncode == 0:
            _log("Worker exited cleanly")
            return 0

        _log(
            f"Worker exited with code {result.returncode} on attempt {attempt}/{attempts}"
        )
        if attempt < attempts:
            _log(f"Retrying in {backoff}s...")
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)

    return result.returncode


def main() -> None:
    """Entry point used by docker-compose and other orchestration tools."""
    engine = os.getenv("PYJOBKIT_ENGINE", "app.task_engine:engine")
    db_url = _database_url()

    max_attempts = int(os.getenv("WORKER_START_MAX_ATTEMPTS", DEFAULT_MAX_ATTEMPTS))
    initial_delay = int(os.getenv("WORKER_START_RETRY_DELAY", DEFAULT_INITIAL_DELAY))
    db_attempts = int(
        os.getenv("WORKER_DB_CHECK_ATTEMPTS", DEFAULT_DB_CHECK_ATTEMPTS)
    )

    _log(
        "Launching worker with retries: "
        f"max_attempts={max_attempts}, initial_delay={initial_delay}s, "
        f"db_attempts={db_attempts}"
    )

    asyncio.run(_wait_for_db(db_url, attempts=db_attempts, delay=initial_delay))

    exit_code = _run_worker(engine, db_url, attempts=max_attempts, delay=initial_delay)
    if exit_code != 0:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
