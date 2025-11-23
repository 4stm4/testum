# SPDX-License-Identifier: MIT
"""Platform API endpoints (in-memory)."""
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route, Router

from app.storage import storage

router = Router()

def _platform_payload(data: dict):
    required = ["name", "host", "port", "username", "auth_method"]
    if not all(data.get(f) for f in required):
        return None
    return {
        "name": data["name"],
        "host": data["host"],
        "port": data.get("port", 22),
        "username": data["username"],
        "auth_method": data["auth_method"],
        "password": data.get("password"),
        "ssh_key_id": data.get("ssh_key_id"),
    }


async def create_platform(request: Request):
    data = await request.json()
    payload = _platform_payload(data)
    if not payload:
        return JSONResponse({"error": "Invalid platform data"}, status_code=400)
    created = storage.create_platform(payload)
    created["has_password"] = bool(created.get("password"))
    created["has_private_key"] = bool(created.get("ssh_key_id"))
    return JSONResponse(created, status_code=201)


async def list_platforms(request: Request):
    items = storage.list_platforms()
    return JSONResponse(items)


async def get_platform(request: Request):
    platform_id = request.path_params.get("platform_id")
    platform = storage.get_platform(platform_id)
    if not platform:
        return JSONResponse({"error": "Platform not found"}, status_code=404)
    return JSONResponse(platform)


async def delete_platform(request: Request):
    platform_id = request.path_params.get("platform_id")
    removed = storage.delete_platform(platform_id)
    if not removed:
        return JSONResponse({"error": "Platform not found"}, status_code=404)
    return JSONResponse({"message": f"Platform {removed['name']} deleted"})


routes = [
    Route("/", list_platforms, methods=["GET"]),
    Route("/", create_platform, methods=["POST"]),
    Route("/{platform_id:uuid}", get_platform, methods=["GET"]),
    Route("/{platform_id:uuid}", delete_platform, methods=["DELETE"]),
]

platforms_router = Router(routes=routes)

tasks_router = Router(routes=[])
