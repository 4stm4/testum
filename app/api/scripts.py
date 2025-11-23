# SPDX-License-Identifier: MIT
"""Script API endpoints (in-memory)."""
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route, Router

from app.storage import storage

router = Router()

def _script_payload(data: dict):
    required = ["name", "language", "content"]
    if not all(data.get(f) for f in required):
        return None
    return {
        "name": data["name"],
        "language": data.get("language", "bash"),
        "description": data.get("description"),
        "content": data["content"],
        "created_by": data.get("created_by", "system"),
    }


async def create_script(request: Request):
    data = await request.json()
    payload = _script_payload(data)
    if not payload:
        return JSONResponse({"error": "Invalid script data"}, status_code=400)
    created = storage.create_script(payload)
    return JSONResponse(created, status_code=201)


async def update_script(request: Request):
    script_id = request.path_params.get("script_id")
    updates = await request.json()
    updated = storage.update_script(script_id, updates)
    if not updated:
        return JSONResponse({"error": "Script not found"}, status_code=404)
    return JSONResponse(updated)


async def get_script(request: Request):
    script_id = request.path_params.get("script_id")
    script = storage.get_script(script_id)
    if not script:
        return JSONResponse({"error": "Script not found"}, status_code=404)
    return JSONResponse(script)


async def list_scripts(request: Request):
    return JSONResponse(storage.list_scripts())


async def delete_script(request: Request):
    script_id = request.path_params.get("script_id")
    removed = storage.delete_script(script_id)
    if not removed:
        return JSONResponse({"error": "Script not found"}, status_code=404)
    return JSONResponse({"message": f"Script {removed['name']} deleted"})


routes = [
    Route("/", list_scripts, methods=["GET"]),
    Route("/", create_script, methods=["POST"]),
    Route("/{script_id:uuid}", get_script, methods=["GET"]),
    Route("/{script_id:uuid}", update_script, methods=["PUT"]),
    Route("/{script_id:uuid}", delete_script, methods=["DELETE"]),
]

scripts_router = Router(routes=routes)
