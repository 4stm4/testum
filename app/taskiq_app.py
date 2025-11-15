"""Taskiq broker and scheduler configuration."""
from taskiq import TaskiqScheduler
from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend
from app.config import config

# Parse Redis URL to get host and port
redis_url = config.REDIS_URL or "redis://localhost:6379/0"
# Extract host:port from redis://host:port/db
redis_parts = redis_url.replace("redis://", "").split("/")
redis_host_port = redis_parts[0]

# Create result backend
result_backend = RedisAsyncResultBackend(redis_url=redis_url)

# Create broker with result backend
broker = ListQueueBroker(
    url=redis_url,
    result_backend=result_backend,
    task_id_generator=None,  # Use default UUID generator
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
