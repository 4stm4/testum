# SPDX-License-Identifier: MIT
"""SSH Keys API endpoints (simplified in-memory version)."""
import uuid
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route, Router

from app.storage import storage

router = Router()


async def list_keys(request: Request):
    items = storage.list_keys()
    response = JSONResponse(items)
    response.headers["X-Total-Count"] = str(len(items))
    response.headers["X-Limit"] = ""  # not used
    response.headers["X-Offset"] = "0"
    return response


async def create_key(request: Request):
    data = await request.json()
    name = data.get("name")
    public_key = data.get("public_key")
    if not name or not public_key:
        return JSONResponse({"error": "name and public_key are required"}, status_code=400)
    new_key = storage.create_key(name=name, public_key=public_key)
    return JSONResponse(new_key, status_code=201)


async def delete_key(request: Request):
    key_id = request.path_params.get("key_id")
    removed = storage.delete_key(key_id)
    if not removed:
        return JSONResponse({"error": "Key not found"}, status_code=404)
    return JSONResponse({"message": f"Key {removed['name']} deleted successfully"})


routes = [
    Route("/", list_keys, methods=["GET"]),
    Route("/", create_key, methods=["POST"]),
    Route("/{key_id:uuid}", delete_key, methods=["DELETE"]),
]

keys_router = Router(routes=routes)
