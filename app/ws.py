"""WebSocket endpoint for streaming task output."""
import asyncio
import json
import logging
from starlette.websockets import WebSocket, WebSocketDisconnect
import redis.asyncio as aioredis

from app.config import config

logger = logging.getLogger(__name__)


async def task_stream_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for streaming task output.

    URL: /ws/tasks/{task_id}
    
    Clients connect and receive real-time updates from Celery tasks
    via Redis pub/sub.
    """
    await websocket.accept()
    
    # Get task ID from path
    task_id = websocket.path_params.get("task_id")
    if not task_id:
        await websocket.send_json({"error": "Missing task_id"})
        await websocket.close()
        return

    channel_name = f"task:{task_id}"
    logger.info(f"WebSocket client connected for task: {task_id}")

    # Create Redis client
    redis_client = await aioredis.from_url(config.REDIS_URL)
    pubsub = redis_client.pubsub()

    try:
        # Subscribe to Redis channel
        await pubsub.subscribe(channel_name)
        logger.info(f"Subscribed to Redis channel: {channel_name}")

        # Send initial connection message
        await websocket.send_json({
            "ts": "",
            "type": "progress",
            "payload": f"Connected to task stream: {task_id}",
        })

        # Listen for messages
        async def redis_listener():
            """Listen for Redis pub/sub messages."""
            try:
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        data = message["data"].decode("utf-8")
                        logger.debug(f"Received from Redis: {data}")
                        
                        # Forward to WebSocket client
                        try:
                            await websocket.send_text(data)
                        except Exception as e:
                            logger.error(f"Failed to send to WebSocket: {e}")
                            break
            except Exception as e:
                logger.error(f"Redis listener error: {e}")

        # Start listener task
        listener_task = asyncio.create_task(redis_listener())

        # Keep connection alive and handle incoming messages (if any)
        try:
            while True:
                # Wait for client messages (or disconnection)
                try:
                    await websocket.receive_text()
                except WebSocketDisconnect:
                    logger.info(f"Client disconnected from task: {task_id}")
                    break
        finally:
            # Cancel listener task
            listener_task.cancel()
            try:
                await listener_task
            except asyncio.CancelledError:
                pass

    except Exception as e:
        logger.error(f"WebSocket error for task {task_id}: {e}")
        try:
            await websocket.send_json({"error": str(e)})
        except Exception:
            pass
    finally:
        # Cleanup
        try:
            await pubsub.unsubscribe(channel_name)
            await pubsub.close()
            await redis_client.close()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

        try:
            await websocket.close()
        except Exception:
            pass

        logger.info(f"WebSocket connection closed for task: {task_id}")
