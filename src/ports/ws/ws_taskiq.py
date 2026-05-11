# SPDX-License-Identifier: MIT
import asyncio
import logging
from datetime import datetime
from starlette.websockets import WebSocket, WebSocketDisconnect

from app.db import SessionLocal
from app.models import TaskRun, TaskStatusEnum

logger = logging.getLogger(__name__)


async def task_stream_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for streaming task output via polling TaskRun.
    
    URL: /ws/tasks/{task_id}
    
    Polls database for task status and output updates.
    """
    await websocket.accept()
    
    # Get task ID from path
    task_id = websocket.path_params.get("task_id")
    if not task_id:
        await websocket.send_json({"error": "Missing task_id"})
        await websocket.close()
        return

    logger.info(f"WebSocket client connected for task: {task_id}")
    
    # Send initial connection message
    await websocket.send_json({
        "type": "progress",
        "payload": "Connected to task stream",
        "ts": datetime.utcnow().isoformat(),
    })

    last_stdout_length = 0
    last_stderr_length = 0
    last_status = None
    poll_interval = 0.5  # Poll every 500ms
    
    try:
        while True:
            # Check for client disconnection
            try:
                # Non-blocking check for incoming messages (ping/disconnect)
                message = await asyncio.wait_for(
                    websocket.receive_text(), 
                    timeout=0.01
                )
                # If client sends "close", disconnect
                if message == "close":
                    break
            except asyncio.TimeoutError:
                pass  # No message, continue polling
            except WebSocketDisconnect:
                logger.info(f"Client disconnected from task: {task_id}")
                break
            
            # Poll database for task updates
            db = SessionLocal()
            try:
                task = db.query(TaskRun).filter(TaskRun.id == task_id).first()
                
                if not task:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Task not found",
                    })
                    break
                
                status_value = task.status.value if task.status else "unknown"
                now_ts = datetime.utcnow().isoformat()

                # Send status update if changed
                if last_status != task.status:
                    await websocket.send_json({
                        "type": "progress",
                        "payload": f"Status: {status_value}",
                        "ts": now_ts,
                    })
                    last_status = task.status

                # Stream stdout/stderr increments
                stdout_value = task.stdout or ""
                if len(stdout_value) > last_stdout_length:
                    new_stdout = stdout_value[last_stdout_length:]
                    await websocket.send_json({
                        "type": "stdout",
                        "payload": new_stdout,
                        "ts": now_ts,
                    })
                    last_stdout_length = len(stdout_value)

                stderr_value = task.stderr or ""
                if len(stderr_value) > last_stderr_length:
                    new_stderr = stderr_value[last_stderr_length:]
                    await websocket.send_json({
                        "type": "stderr",
                        "payload": new_stderr,
                        "ts": now_ts,
                    })
                    last_stderr_length = len(stderr_value)

                # If task is finished, send completion and close
                if task.status in [TaskStatusEnum.SUCCESS, TaskStatusEnum.FAILED]:
                    payload = (
                        task.error_message or "Task completed successfully"
                        if task.status == TaskStatusEnum.SUCCESS
                        else task.error_message or "Task failed"
                    )
                    await websocket.send_json({
                        "type": "done" if task.status == TaskStatusEnum.SUCCESS else "error",
                        "payload": payload,
                        "ts": now_ts,
                    })
                    break
                    
            finally:
                db.close()
            
            # Wait before next poll
            await asyncio.sleep(poll_interval)
            
    except WebSocketDisconnect:
        logger.info(f"Client disconnected from task: {task_id}")
    except Exception as e:
        logger.error(f"WebSocket error for task {task_id}: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e),
            })
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
        
        logger.info(f"WebSocket connection closed for task: {task_id}")
