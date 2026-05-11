
# SPDX-License-Identifier: MIT
"""Main Starlette application."""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path
import jwt
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from ports.api.automations import automations_router
from ports.api.virt import virt_router
from ports.api.audit import audit_router
from ports.api.backup import backup_router
from ports.api.gitops import gitops_router
from ports.api.keys import keys_router
from ports.api.platforms import platforms_router, tasks_router
from ports.api.scripts import scripts_router
from ports.api.users import users_router
from app.auth import AuthMiddleware
from app.config import config
from app import db as app_db
from app.models import User, UserRole
from app.rate_limiter import RateLimiterMiddleware
from app.rbac import get_request_user
from app.security import hash_password, verify_password
from app.updater import UpdateError, get_update_info, perform_update
from app.db import SessionLocal
from app.models import AutomationJob, Platform, SSHKey, Script, TaskRun, TaskStatusEnum
from ports.ws.ws_taskiq import task_stream_websocket
from app.task_engine import backend, engine


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "name": "%(name)s", "message": "%(message)s"}',
)
logger = logging.getLogger(__name__)


_WEB_PORT = Path(__file__).parent.parent / "ports" / "web"  # src/app -> src/ports/web

# Templates
templates = Jinja2Templates(directory=str(_WEB_PORT / "templates"))


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
def _mark_stale_tasks_failed() -> None:
    """Mark any tasks left in RUNNING/PENDING state from a previous process as FAILED.

    Background tasks (e.g. libvirt install) are fire-and-forget; if the server
    was killed mid-run they stay RUNNING forever.  On startup we flip them to
    FAILED so the UI doesn't show a permanently spinning job.
    """
    from datetime import datetime as _dt
    with app_db.SessionLocal() as db:
        stale = (
            db.query(TaskRun)
            .filter(TaskRun.status.in_([TaskStatusEnum.RUNNING, TaskStatusEnum.PENDING]))
            .all()
        )
        if stale:
            for task in stale:
                task.status = TaskStatusEnum.FAILED
                task.finished_at = task.finished_at or _dt.utcnow()
                task.stdout = (task.stdout or "") + "\n[Marked failed on server restart]\n"
            db.commit()
            logger.warning("Marked %d stale task(s) as FAILED on startup", len(stale))


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


async def users_page(request: Request):
    """User management page (admin only)."""
    user = get_request_user(request)
    if not user or not user.is_admin():
        return JSONResponse({"error": "Admin access required"}, status_code=403)
    
    return templates.TemplateResponse(
        "users.html", build_template_context(request, "users")
    )


async def audit_page(request: Request):
    """Audit logs page (admin/operator only)."""
    user = get_request_user(request)
    if not user or user.role == UserRole.VIEWER:
        return JSONResponse({"error": "Admin or Operator access required"}, status_code=403)
    
    return templates.TemplateResponse(
        "audit.html", build_template_context(request, "audit")
    )


async def jobs_page(request: Request):
    """Jobs page listing recent tasks."""
    return templates.TemplateResponse(
        "jobs.html", build_template_context(request, "jobs")
    )


async def virt_vms_page(request: Request):
    return templates.TemplateResponse("virt_vms.html", build_template_context(request, "virt_vms"))


async def virt_pools_page(request: Request):
    return templates.TemplateResponse("virt_pools.html", build_template_context(request, "virt_pools"))


async def virt_volumes_page(request: Request):
    return templates.TemplateResponse("virt_volumes.html", build_template_context(request, "virt_volumes"))


async def virt_ufw_page(request: Request):
    return templates.TemplateResponse("virt_ufw.html", build_template_context(request, "virt_ufw"))


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
        context = build_template_context(request, "health", health=health_data)
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
    Route("/virt/vms", virt_vms_page),
    Route("/virt/pools", virt_pools_page),
    Route("/virt/ufw", virt_ufw_page),
    Route("/virt/volumes", virt_volumes_page),
    Route("/audit", audit_page),
    Route("/users", users_page),
    Route("/settings", settings_page),
    Route("/tasks/{task_id}", task_page),
    Route("/health", health_check),
    WebSocketRoute("/ws/tasks/{task_id}", task_stream_websocket),
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
    Mount("/api/audit", audit_router),
    Mount("/api/backup", backup_router),
    Mount("/api/gitops", gitops_router),
    Mount("/api/virt", virt_router),
    Mount("/static", StaticFiles(directory=str(_WEB_PORT / "static")), name="static"),
]

app = Starlette(
    debug=config.APP_ENV == "development",
    routes=routes,
    middleware=middleware,
)


_background_tasks: list = []


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize application services."""
    ensure_default_admin_user()
    _mark_stale_tasks_failed()

    # Start the pyjobkit worker in-process so commands and deploys work
    # without a separate worker container (useful for local dev and single-
    # container deployments).  In Docker the dedicated worker container is
    # preferred; running both is harmless — only one will claim each job.
    from pyjobkit.worker import Worker
    from app.scheduler import run_scheduler, run_system_info_refresher

    worker = Worker(engine)

    async def _run_worker():
        try:
            await worker.run()
        except Exception:
            logger.exception("In-process worker crashed")

    async def _run_scheduler():
        try:
            await run_scheduler()
        except Exception:
            logger.exception("In-process scheduler crashed")

    async def _run_refresher():
        try:
            await run_system_info_refresher()
        except Exception:
            logger.exception("In-process system_info refresher crashed")

    for coro in (_run_worker, _run_scheduler, _run_refresher):
        task = asyncio.create_task(coro())
        _background_tasks.append(task)

    logger.info("In-process worker, scheduler and refresher started")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    for task in _background_tasks:
        task.cancel()


logger.info(f"Application started in {config.APP_ENV} mode")
