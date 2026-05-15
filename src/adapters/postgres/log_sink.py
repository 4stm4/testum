# SPDX-License-Identifier: MIT
"""Postgres-backed LogSink that writes pyjobkit log records to TaskRun.stdout.

Lines are batched with a 100 ms debounce to avoid a DB round-trip per log
line. A flush also fires whenever the in-flight buffer reaches 20 lines.
"""
from __future__ import annotations

import asyncio
import logging
from typing import List

from pyjobkit.contracts import LogRecord, LogSink

logger = logging.getLogger(__name__)

_FLUSH_INTERVAL = 0.1   # seconds
_FLUSH_BATCH    = 20    # lines


class TaskRunLogSink(LogSink):
    """Append pyjobkit log lines to ``TaskRun.stdout`` in batches."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[LogRecord] = asyncio.Queue()
        self._flusher_task: asyncio.Task | None = None

    # ── LogSink contract ───────────────────────────────────────────────────

    async def write(self, record: LogRecord) -> None:
        await self._queue.put(record)
        # Ensure the background flusher is running.
        if self._flusher_task is None or self._flusher_task.done():
            self._flusher_task = asyncio.create_task(self._flusher())

    # ── Background flusher ─────────────────────────────────────────────────

    async def _flusher(self) -> None:
        """Drain the queue periodically or when the batch threshold is hit."""
        while True:
            records: List[LogRecord] = []

            # Wait up to _FLUSH_INTERVAL for the first item.
            try:
                first = await asyncio.wait_for(self._queue.get(), timeout=_FLUSH_INTERVAL)
                records.append(first)
            except asyncio.TimeoutError:
                # Nothing arrived in the interval — queue is idle.
                if self._queue.empty():
                    return
                continue

            # Drain any additional items already in the queue up to batch limit.
            while not self._queue.empty() and len(records) < _FLUSH_BATCH:
                records.append(self._queue.get_nowait())

            if records:
                try:
                    await asyncio.to_thread(self._flush_sync, records)
                except Exception:
                    logger.exception("TaskRunLogSink: error flushing %d records", len(records))

    # ── Sync DB write (runs in a thread) ───────────────────────────────────

    @staticmethod
    def _flush_sync(records: List[LogRecord]) -> None:
        from adapters.postgres.session import SessionLocal
        from adapters.postgres.orm_models import TaskRunRow

        # Group by job_id string to minimise DB queries.
        from collections import defaultdict
        by_job: dict[str, list[str]] = defaultdict(list)
        for rec in records:
            by_job[str(rec.job_id)].append(rec.message)

        with SessionLocal() as db:
            for job_id_str, messages in by_job.items():
                row: TaskRunRow | None = (
                    db.query(TaskRunRow)
                    .filter(TaskRunRow.pyjobkit_job_id == job_id_str)
                    .first()
                )
                if row is None:
                    logger.debug(
                        "TaskRunLogSink: no TaskRun for pyjobkit_job_id=%s", job_id_str
                    )
                    continue
                appended = "\n".join(messages) + "\n"
                row.stdout = (row.stdout or "") + appended
            db.commit()

    # ── Optional graceful close ────────────────────────────────────────────

    async def close(self) -> None:
        """Flush remaining records and stop the flusher task."""
        # Drain whatever is left.
        remaining: List[LogRecord] = []
        while not self._queue.empty():
            remaining.append(self._queue.get_nowait())
        if remaining:
            try:
                await asyncio.to_thread(self._flush_sync, remaining)
            except Exception:
                logger.exception("TaskRunLogSink.close: error flushing remaining records")
        if self._flusher_task and not self._flusher_task.done():
            self._flusher_task.cancel()
