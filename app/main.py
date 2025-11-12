"""Main Starlette application."""
import logging
from starlette.applications import Starlette
from starlette.routing import Route, Mount, WebSocketRoute
from starlette.responses import JSONResponse, RedirectResponse
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
import jwt
from datetime import datetime, timedelta

from app.config import config
from app.api.keys import keys_router
from app.api.platforms import platforms_router, tasks_router
from app.ws import task_stream_websocket
from app.auth import AuthMiddleware
from app.updater import get_update_info, perform_update, UpdateError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "name": "%(name)s", "message": "%(message)s"}',
)
logger = logging.getLogger(__name__)

# Templates
templates = Jinja2Templates(directory="app/templates")


# Middleware
middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    ),
    Middleware(AuthMiddleware),
]


# Auth helpers
def create_jwt_token(username: str) -> str:
    """Create JWT token."""
    payload = {
        "sub": username,
        "exp": datetime.utcnow() + timedelta(hours=24),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, config.SECRET_KEY, algorithm="HS256")


def verify_jwt_token(token: str) -> dict:
    """Verify JWT token."""
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token expired")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token")


# Routes
async def homepage(request: Request):
    """Homepage with links to keys and platforms."""
    return templates.TemplateResponse("index.html", {"request": request, "active_page": "dashboard"})


async def keys_page(request: Request):
    """SSH Keys page."""
    return templates.TemplateResponse("keys.html", {"request": request, "active_page": "keys"})


async def platforms_page(request: Request):
    """Platforms page."""
    return templates.TemplateResponse("platforms.html", {"request": request, "active_page": "platforms"})


async def settings_page(request: Request):
    """Settings page."""
    return templates.TemplateResponse("settings.html", {"request": request, "active_page": "settings"})


async def jobs_page(request: Request):
    """Jobs page listing recent tasks."""
    return templates.TemplateResponse("jobs.html", {"request": request, "active_page": "jobs"})


async def job_detail_page(request: Request):
    """Job detail page for a specific task."""
    task_id = request.path_params.get("task_id")
    return templates.TemplateResponse("job-detail.html", {"request": request, "task_id": task_id, "active_page": "jobs"})


async def task_page(request: Request):
    """Task monitoring page."""
    task_id = request.path_params.get("task_id")
    return templates.TemplateResponse("task.html", {"request": request, "task_id": task_id, "active_page": "jobs"})


async def login_page(request: Request):
    """Login page."""
    return templates.TemplateResponse("login.html", {"request": request})


async def login_endpoint(request: Request):
    """Simple login endpoint."""
    data = await request.json()
    username = data.get("username")
    password = data.get("password")

    # Simple auth check (for MVP)
    if username == config.ADMIN_USERNAME and password == config.ADMIN_PASSWORD:
        token = create_jwt_token(username)
        return JSONResponse({
            "access_token": token,
            "token_type": "bearer",
        })
    else:
        return JSONResponse({"error": "Invalid credentials"}, status_code=401)


async def logout_endpoint(request: Request):
    """Logout endpoint - clears the cookie."""
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("access_token")
    return response


async def change_username_endpoint(request: Request):
    """Change username endpoint."""
    data = await request.json()
    current_password = data.get("current_password")
    new_username = data.get("new_username")
    
    if not current_password or not new_username:
        return JSONResponse({"error": "Missing required fields"}, status_code=400)
    
    # Verify current password
    if current_password != config.ADMIN_PASSWORD:
        return JSONResponse({"error": "Invalid current password"}, status_code=401)
    
    # Validate new username
    if len(new_username) < 3:
        return JSONResponse({"error": "Username must be at least 3 characters"}, status_code=400)
    
    # Update username in environment (this is temporary - ideally update in config file or DB)
    # For MVP, we need to update the docker-compose.yml or restart with new env vars
    # For now, just return success - user needs to update ADMIN_USERNAME in deployment
    
    return JSONResponse({
        "message": "Username change requested",
        "note": "Please update ADMIN_USERNAME environment variable in your deployment configuration"
    })


async def change_password_endpoint(request: Request):
    """Change password endpoint."""
    data = await request.json()
    current_password = data.get("current_password")
    new_password = data.get("new_password")
    
    if not current_password or not new_password:
        return JSONResponse({"error": "Missing required fields"}, status_code=400)
    
    # Verify current password
    if current_password != config.ADMIN_PASSWORD:
        return JSONResponse({"error": "Invalid current password"}, status_code=401)
    
    # Validate new password
    if len(new_password) < 8:
        return JSONResponse({"error": "Password must be at least 8 characters"}, status_code=400)
    
    # Update password in environment (this is temporary - ideally update in config file or DB)
    # For MVP, we need to update the docker-compose.yml or restart with new env vars
    # For now, just return success - user needs to update ADMIN_PASSWORD in deployment
    
    return JSONResponse({
        "message": "Password change requested",
        "note": "Please update ADMIN_PASSWORD environment variable in your deployment configuration"
    })


async def get_settings_endpoint(request: Request):
    """Get current system settings (non-sensitive)."""
    # Mask sensitive values
    def mask_connection_string(url: str) -> str:
        """Mask password in connection string."""
        if '@' in url:
            parts = url.split('@')
            if '://' in parts[0]:
                protocol_user = parts[0].split('://')
                if ':' in protocol_user[1]:
                    user = protocol_user[1].split(':')[0]
                    return f"{protocol_user[0]}://{user}:••••••@{parts[1]}"
        return url
    
    return JSONResponse({
        "app_env": config.APP_ENV,
        "admin_username": config.ADMIN_USERNAME,
        "database_url": mask_connection_string(config.DATABASE_URL),
        "redis_url": mask_connection_string(config.REDIS_URL),
        "celery_broker_url": mask_connection_string(config.CELERY_BROKER_URL),
        "celery_result_backend": mask_connection_string(config.CELERY_RESULT_BACKEND),
        "minio_endpoint": config.MINIO_ENDPOINT,
        "minio_bucket": config.MINIO_BUCKET,
        "minio_secure": config.MINIO_SECURE,
        "ssh_host_key_policy": config.SSH_HOST_KEY_POLICY,
    })


async def health_check(request: Request):
    """Health check endpoint with HTML and JSON responses."""
    health_data = {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

    accept_header = request.headers.get("accept", "")
    wants_html = "text/html" in accept_header and "application/json" not in accept_header

    if wants_html:
        context = {"request": request, "active_page": "health", "health": health_data}
        return templates.TemplateResponse("health.html", context)

    return JSONResponse(health_data)


async def check_updates_endpoint(request: Request):
    """Check for available updates from GitHub."""
    try:
        update_info = await get_update_info()
        return JSONResponse(update_info)
    except UpdateError as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    except Exception as e:
        logger.error(f"Unexpected error checking updates: {e}")
        return JSONResponse({"error": "Internal server error"}, status_code=500)


async def perform_update_endpoint(request: Request):
    """Perform update from GitHub."""
    try:
        data = await request.json()
        target_version = data.get("target_version")  # Optional: specific version tag
        
        result = await perform_update(target_version=target_version)
        return JSONResponse(result)
    except UpdateError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        logger.error(f"Unexpected error performing update: {e}")
        return JSONResponse({"error": "Internal server error"}, status_code=500)


# Create application
routes = [
    Route("/", homepage),
    Route("/login", login_page),
    Route("/keys", keys_page),
    Route("/platforms", platforms_page),
    Route("/jobs", jobs_page),
    Route("/jobs/{task_id}", job_detail_page),
    Route("/settings", settings_page),
    Route("/tasks/{task_id}", task_page),
    Route("/health", health_check),
    Route("/api/auth/login", login_endpoint, methods=["POST"]),
    Route("/api/auth/logout", logout_endpoint, methods=["GET", "POST"]),
    Route("/api/auth/change-username", change_username_endpoint, methods=["POST"]),
    Route("/api/auth/change-password", change_password_endpoint, methods=["POST"]),
    Route("/api/settings", get_settings_endpoint, methods=["GET"]),
    Route("/api/updates/check", check_updates_endpoint, methods=["GET"]),
    Route("/api/updates/perform", perform_update_endpoint, methods=["POST"]),
    Mount("/api/keys", keys_router),
    Mount("/api/platforms", platforms_router),
    Mount("/api/tasks", tasks_router),
    Mount("/static", StaticFiles(directory="app/templates"), name="static"),
    WebSocketRoute("/ws/tasks/{task_id}", task_stream_websocket),
]

app = Starlette(
    debug=config.APP_ENV == "development",
    routes=routes,
    middleware=middleware,
)

logger.info(f"Application started in {config.APP_ENV} mode")
