# SPDX-License-Identifier: MIT
"""WebSocket task output streaming via DB polling."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from starlette.websockets import WebSocket, WebSocketDisconnect

from core.domain.enums import TaskStatus
from core.interfaces.storage import Storage

logger = logging.getLogger(__name__)


async def task_stream_websocket(websocket: WebSocket, storage: Storage) -> None:
    await websocket.accept()

    task_id = websocket.path_params.get("task_id")
    if not task_id:
        await websocket.send_json({"error": "Missing task_id"})
        await websocket.close()
        return

    logger.info("WS connected for task: %s", task_id)
    await websocket.send_json({
        "type": "progress",
        "payload": "Connected to task stream",
        "ts": datetime.utcnow().isoformat(),
    })

    last_stdout_len = 0
    last_stderr_len = 0
    last_status = None

    try:
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=0.01)
                if msg == "close":
                    break
            except asyncio.TimeoutError:
                pass
            except WebSocketDisconnect:
                break

            task = storage.get_task_run_by_id(task_id)
            if not task:
                await websocket.send_json({"type": "error", "message": "Task not found"})
                break

            now = datetime.utcnow().isoformat()

            if last_status != task.status:
                await websocket.send_json({
                    "type": "progress",
                    "payload": f"Status: {task.status.value}",
                    "ts": now,
                })
                last_status = task.status

            stdout = task.stdout or ""
            if len(stdout) > last_stdout_len:
                await websocket.send_json({
                    "type": "stdout",
                    "payload": stdout[last_stdout_len:],
                    "ts": now,
                })
                last_stdout_len = len(stdout)

            stderr = task.stderr or ""
            if len(stderr) > last_stderr_len:
                await websocket.send_json({
                    "type": "stderr",
                    "payload": stderr[last_stderr_len:],
                    "ts": now,
                })
                last_stderr_len = len(stderr)

            if task.status in (TaskStatus.SUCCESS, TaskStatus.FAILED):
                msg_type = "done" if task.status == TaskStatus.SUCCESS else "error"
                await websocket.send_json({
                    "type": msg_type,
                    "payload": task.error_message or ("Task completed" if msg_type == "done" else "Task failed"),
                    "ts": now,
                })
                break

            await asyncio.sleep(0.5)

    except WebSocketDisconnect:
        logger.info("WS client disconnected for task: %s", task_id)
    except Exception as exc:
        logger.error("WS error for task %s: %s", task_id, exc)
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
