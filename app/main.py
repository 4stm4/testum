# SPDX-License-Identifier: MIT
"""Minimal application entrypoint for tests."""
import uuid
from datetime import datetime
import jwt
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
from starlette.routing import Mount, Route
from starlette.templating import Jinja2Templates
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from app.api.keys import keys_router
from app.api.platforms import platforms_router, tasks_router
from app.api.scripts import scripts_router
from app.api.automations import automations_router
from app.storage import storage

templates = Jinja2Templates(directory="app/templates")

middleware = [Middleware(CORSMiddleware)]


def create_jwt_token(user_id: str, username: str, role: str = "admin") -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "exp": datetime.utcnow().isoformat(),
    }
    return jwt.encode(payload, "secret", algorithm="HS256")


def verify_jwt_token(token: str):
    try:
        return jwt.decode(token, "secret", algorithms=["HS256"])
    except Exception:
        raise ValueError("Invalid token")


async def homepage(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


async def health_check(request: Request):
    return JSONResponse({"status": "healthy", "timestamp": datetime.utcnow().isoformat()})


async def login_endpoint(request: Request):
    data = await request.json()
    username = data.get("username", "admin")
    token = create_jwt_token(str(uuid.uuid4()), username, "admin")
    response = JSONResponse({"access_token": token})
    return response


async def logout_endpoint(request: Request):
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("access_token")
    return response


routes = [
    Route("/", homepage),
    Route("/health", health_check),
    Route("/api/auth/login", login_endpoint, methods=["POST"]),
    Route("/api/auth/logout", logout_endpoint, methods=["GET", "POST"]),
    Mount("/api/keys", keys_router),
    Mount("/api/platforms", platforms_router),
    Mount("/api/scripts", scripts_router),
    Mount("/api/automations", automations_router),
    Mount("/api/tasks", tasks_router),
]

app = Starlette(routes=routes, middleware=middleware, debug=True)


async def startup_event():
    storage.reset()


app.on_event("startup")(startup_event)
