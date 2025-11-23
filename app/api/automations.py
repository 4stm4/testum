# SPDX-License-Identifier: MIT
"""Automation job API endpoints (in-memory)."""
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route, Router

from app.storage import storage

router = Router()

def _automation_payload(data: dict):
    required = ["name", "execution_type", "trigger_type"]
    if not all(data.get(f) is not None for f in required):
        return None
    return data.copy()


async def list_automations(request: Request):
    return JSONResponse(storage.list_automations())


async def create_automation(request: Request):
    data = await request.json()
    payload = _automation_payload(data)
    if not payload:
        return JSONResponse({"error": "Invalid automation"}, status_code=400)
    created = storage.create_automation(payload)
    return JSONResponse(created, status_code=201)


async def update_automation(request: Request):
    automation_id = request.path_params.get("automation_id")
    updates = await request.json()
    updated = storage.update_automation(automation_id, updates)
    if not updated:
        return JSONResponse({"error": "Automation not found"}, status_code=404)
    return JSONResponse(updated)


async def delete_automation(request: Request):
    automation_id = request.path_params.get("automation_id")
    removed = storage.delete_automation(automation_id)
    if not removed:
        return JSONResponse({"error": "Automation not found"}, status_code=404)
    return JSONResponse({"message": f"Automation {removed['name']} deleted"})


routes = [
    Route("/", list_automations, methods=["GET"]),
    Route("/", create_automation, methods=["POST"]),
    Route("/{automation_id:uuid}", update_automation, methods=["PUT"]),
    Route("/{automation_id:uuid}", delete_automation, methods=["DELETE"]),
]

automations_router = Router(routes=routes)
