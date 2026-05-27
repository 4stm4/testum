"""T5: Operation bridge — track Nervum operations as Testum sdn_tasks.

Usage:
    task = await create_sdn_task(operation_id, project_id=..., kind=...,
                                  resource_type=..., resource_id=..., initiated_by=...)
    await watch_sdn_task(task.id)   # background: polls until terminal
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime

from adapters.nervum.client import NervumClient
from adapters.postgres.orm_models import SdnTaskRow
from app.db import SessionLocal

logger = logging.getLogger(__name__)

_TERMINAL = {"succeeded", "failed", "cancelled", "rolled_back"}
_POLL_INTERVAL = 3.0
_POLL_TIMEOUT  = 600.0


def create_sdn_task(
    nervum_operation_id: str,
    *,
    testum_task_id: str | None = None,
    project_id: str | None = None,
    kind: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    initiated_by: str | None = None,
) -> SdnTaskRow:
    """Persist a new sdn_task row and return it (sync — call from async context)."""
    with SessionLocal() as db:
        row = SdnTaskRow(
            id=uuid.uuid4(),
            testum_task_id=testum_task_id,
            nervum_operation_id=nervum_operation_id,
            project_id=project_id,
            kind=kind,
            resource_type=resource_type,
            resource_id=resource_id,
            status="accepted",
            initiated_by=initiated_by,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row


def _update_sdn_task(task_id: str, op: dict) -> None:
    """Sync-update sdn_task from a OperationOut dict."""
    status = op.get("status", "accepted")
    error  = op.get("error")
    with SessionLocal() as db:
        row = db.query(SdnTaskRow).filter(SdnTaskRow.id == task_id).first()
        if not row:
            return
        row.status = status
        row.updated_at = datetime.utcnow()
        if status in _TERMINAL:
            row.finished_at = datetime.utcnow()
        if error:
            row.error_code    = error.get("code")
            row.error_message = error.get("message")
        # back-fill resource info from operation if missing
        res = op.get("resource", {})
        if res.get("type") and not row.resource_type:
            row.resource_type = res["type"]
        if res.get("id") and not row.resource_id:
            row.resource_id = res["id"]
        if op.get("kind") and not row.kind:
            row.kind = op["kind"]
        db.commit()


async def watch_sdn_task(task_id: str) -> None:
    """Background coroutine: poll Nervum until operation is terminal, then update row."""
    client = NervumClient()

    with SessionLocal() as db:
        row = db.query(SdnTaskRow).filter(SdnTaskRow.id == task_id).first()
        if not row:
            return
        operation_id = row.nervum_operation_id

    try:
        op = await client.poll_operation(
            operation_id,
            poll_interval=_POLL_INTERVAL,
            timeout=_POLL_TIMEOUT,
        )
        _update_sdn_task(task_id, op)
        logger.info(
            "sdn_task %s: operation %s → %s",
            task_id, operation_id, op.get("status"),
        )
    except Exception:
        logger.exception(
            "sdn_task %s: poll_operation %s failed", task_id, operation_id
        )
        with SessionLocal() as db:
            row = db.query(SdnTaskRow).filter(SdnTaskRow.id == task_id).first()
            if row and row.status not in _TERMINAL:
                row.status        = "failed"
                row.error_message = "poll timeout or connection error"
                row.finished_at   = datetime.utcnow()
                db.commit()


def spawn_watch(task_id: str) -> None:
    """Schedule watch_sdn_task as a background asyncio task."""
    asyncio.create_task(watch_sdn_task(task_id))
