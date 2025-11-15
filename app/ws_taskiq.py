# SPDX-License-Identifier: MIT
"""WebSocket endpoint for streaming task output via Taskiq state."""
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
        "type": "connected",
        "task_id": task_id,
        "timestamp": datetime.utcnow().isoformat(),
    })

    last_output_length = 0
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
                
                # Send status update if changed
                if last_status != task.status:
                    await websocket.send_json({
                        "type": "status",
                        "status": task.status.value if task.status else "unknown",
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                    last_status = task.status
                
                # Send new output if available
                current_output = task.output or ""
                if len(current_output) > last_output_length:
                    new_output = current_output[last_output_length:]
                    await websocket.send_json({
                        "type": "output",
                        "data": new_output,
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                    last_output_length = len(current_output)
                
                # If task is finished, send completion and close
                if task.status in [TaskStatusEnum.COMPLETED, TaskStatusEnum.FAILED]:
                    await websocket.send_json({
                        "type": "done",
                        "status": task.status.value,
                        "exit_code": task.exit_code,
                        "timestamp": datetime.utcnow().isoformat(),
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
