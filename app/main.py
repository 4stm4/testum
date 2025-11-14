"""Main Starlette application."""
import logging
import uuid
from datetime import datetime, timedelta

import jwt
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from app.api.automations import automations_router
from app.api.keys import keys_router
from app.api.platforms import platforms_router, tasks_router
from app.api.scripts import scripts_router
from app.api.users import users_router
from app.auth import AuthMiddleware
from app.config import config
from app import db as app_db
from app.models import User, UserRole
from app.rate_limiter import RateLimiterMiddleware
from app.rbac import get_request_user
from app.security import hash_password, verify_password
from app.updater import UpdateError, get_update_info, perform_update
from app.ws import task_stream_websocket
from app.updater import get_update_info, perform_update, UpdateError
from app.db import SessionLocal
from app.models import AutomationJob, Platform, SSHKey, Script, TaskRun

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
    Middleware(RateLimiterMiddleware),
    Middleware(AuthMiddleware),
]


# Bootstrap helpers
def ensure_default_admin_user() -> None:
    """Ensure there is at least one administrator user."""

    with app_db.SessionLocal() as db:
        admin = db.query(User).filter(User.username == config.ADMIN_USERNAME).first()

        if not admin:
            admin = User(
                id=uuid.uuid4(),
                username=config.ADMIN_USERNAME,
                hashed_password=hash_password(config.ADMIN_PASSWORD),
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.add(admin)
            db.commit()
            logger.info("Created default admin user '%s'", admin.username)
            return

        updated = False

        if admin.role != UserRole.ADMIN:
            admin.role = UserRole.ADMIN
            updated = True

        if config.ADMIN_PASSWORD and not verify_password(config.ADMIN_PASSWORD, admin.hashed_password):
            admin.hashed_password = hash_password(config.ADMIN_PASSWORD)
            updated = True

        if not admin.is_active:
            admin.is_active = True
            updated = True

        if updated:
            admin.updated_at = datetime.utcnow()
            db.commit()
            logger.info("Synchronized default admin credentials for '%s'", admin.username)


# Auth helpers
def create_jwt_token(user_id: str, username: str, role: UserRole) -> str:
    """Create JWT token for the given user."""

    payload = {
        "sub": user_id,
        "username": username,
        "role": role.value if isinstance(role, UserRole) else str(role),
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


# Helper utilities
def get_sidebar_counts() -> dict:
    """Collect counts for sidebar resources."""

    session = SessionLocal()
    try:
        counts = {
            "keys": 0,
            "platforms": 0,
            "scripts": 0,
            "automations": 0,
            "jobs": 0,
        }
        
        # Try to count each table, handle missing tables gracefully
        try:
            counts["keys"] = session.query(SSHKey).count()
        except Exception:
            pass
        
        try:
            counts["platforms"] = session.query(Platform).count()
        except Exception:
            pass
        
        try:
            counts["scripts"] = session.query(Script).count()
        except Exception:
            pass
        
        try:
            counts["automations"] = session.query(AutomationJob).count()
        except Exception:
            pass
        
        try:
            counts["jobs"] = session.query(TaskRun).count()
        except Exception:
            pass
        
        return counts
    finally:
        session.close()


def build_template_context(request: Request, active_page: str, **extra) -> dict:
    """Build base context for layout-aware templates."""

    context = {"request": request, "active_page": active_page}
    context.update(extra)
    context["sidebar_counts"] = get_sidebar_counts()
    return context


# Routes
async def homepage(request: Request):
    """Homepage with links to keys and platforms."""
    return templates.TemplateResponse(
        "index.html", build_template_context(request, "")
    )


async def keys_page(request: Request):
    """SSH Keys page."""
    return templates.TemplateResponse(
        "keys.html", build_template_context(request, "keys")
    )


async def platforms_page(request: Request):
    """Platforms page."""
    return templates.TemplateResponse(
        "platforms.html", build_template_context(request, "platforms")
    )


async def scripts_page(request: Request):
    """Scripts library page."""
    return templates.TemplateResponse(
        "scripts.html", build_template_context(request, "scripts")
    )


async def automations_page(request: Request):
    """Automation jobs page."""
    return templates.TemplateResponse(
        "automations.html", build_template_context(request, "automations")
    )


async def settings_page(request: Request):
    """Settings page."""
    return templates.TemplateResponse(
        "settings.html", build_template_context(request, "settings")
    )


async def jobs_page(request: Request):
    """Jobs page listing recent tasks."""
    return templates.TemplateResponse(
        "jobs.html", build_template_context(request, "jobs")
    )


async def job_detail_page(request: Request):
    """Job detail page for a specific task."""
    task_id = request.path_params.get("task_id")
    return templates.TemplateResponse(
        "job-detail.html",
        build_template_context(request, "jobs", task_id=task_id),
    )


async def task_page(request: Request):
    """Task monitoring page."""
    task_id = request.path_params.get("task_id")
    return templates.TemplateResponse(
        "task.html",
        build_template_context(request, "jobs", task_id=task_id),
    )


async def login_page(request: Request):
    """Login page."""
    return templates.TemplateResponse("login.html", {"request": request})


async def login_endpoint(request: Request):
    """Simple login endpoint."""
    data = await request.json()
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return JSONResponse({"error": "Username and password are required"}, status_code=400)

    with app_db.SessionLocal() as db:
        user = db.query(User).filter(User.username == username).first()

        if not user or not user.is_active or not verify_password(password, user.hashed_password):
            return JSONResponse({"error": "Invalid credentials"}, status_code=401)

        user.last_login = datetime.utcnow()
        db.commit()

        token = create_jwt_token(str(user.id), user.username, user.role)
        response = JSONResponse(
            {
                "access_token": token,
                "token_type": "bearer",
                "user": {
                    "id": str(user.id),
                    "username": user.username,
                    "role": user.role.value if isinstance(user.role, UserRole) else str(user.role),
                },
            }
        )
        response.set_cookie(
            "access_token",
            token,
            max_age=86400,
            httponly=True,
            secure=config.APP_ENV == "production",
            samesite="lax",
            path="/",
        )
        return response


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

    new_username = new_username.strip()
    if len(new_username) < 3:
        return JSONResponse({"error": "Username must be at least 3 characters"}, status_code=400)

    user_context = get_request_user(request)
    if not user_context:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    with app_db.SessionLocal() as db:
        user = db.query(User).filter(User.id == user_context.id).first()
        if not user:
            return JSONResponse({"error": "User not found"}, status_code=404)

        if not verify_password(current_password, user.hashed_password):
            return JSONResponse({"error": "Invalid current password"}, status_code=401)

        # Ensure username unique
        existing = db.query(User).filter(User.username == new_username, User.id != user.id).first()
        if existing:
            return JSONResponse({"error": "Username already in use"}, status_code=409)

        user.username = new_username
        user.updated_at = datetime.utcnow()
        db.commit()

        token = create_jwt_token(str(user.id), user.username, user.role)
        response = JSONResponse({"message": "Username updated", "access_token": token})
        response.set_cookie(
            "access_token",
            token,
            max_age=86400,
            httponly=True,
            secure=config.APP_ENV == "production",
            samesite="lax",
            path="/",
        )
        return response


async def change_password_endpoint(request: Request):
    """Change password endpoint."""
    data = await request.json()
    current_password = data.get("current_password")
    new_password = data.get("new_password")

    if not current_password or not new_password:
        return JSONResponse({"error": "Missing required fields"}, status_code=400)

    if len(new_password) < 8:
        return JSONResponse({"error": "Password must be at least 8 characters"}, status_code=400)

    user_context = get_request_user(request)
    if not user_context:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    with app_db.SessionLocal() as db:
        user = db.query(User).filter(User.id == user_context.id).first()
        if not user:
            return JSONResponse({"error": "User not found"}, status_code=404)

        if not verify_password(current_password, user.hashed_password):
            return JSONResponse({"error": "Invalid current password"}, status_code=401)

        user.hashed_password = hash_password(new_password)
        user.updated_at = datetime.utcnow()
        db.commit()

        return JSONResponse({"message": "Password updated"})


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
    
    user = get_request_user(request)

    return JSONResponse({
        "app_env": config.APP_ENV,
        "current_user": {
            "username": user.username,
            "role": user.role.value,
        }
        if user
        else None,
        "default_admin_username": config.ADMIN_USERNAME,
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
    Route("/scripts", scripts_page),
    Route("/automations", automations_page),
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
    Mount("/api/scripts", scripts_router),
    Mount("/api/users", users_router),
    Mount("/api/automations", automations_router),
    Mount("/api/tasks", tasks_router),
    Mount("/static", StaticFiles(directory="app/static"), name="static"),
    WebSocketRoute("/ws/tasks/{task_id}", task_stream_websocket),
]

app = Starlette(
    debug=config.APP_ENV == "development",
    routes=routes,
    middleware=middleware,
)


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize application services."""

    ensure_default_admin_user()


logger.info(f"Application started in {config.APP_ENV} mode")
