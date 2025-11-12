"""Reusable automation scripts API endpoints."""
import uuid
from datetime import datetime
from typing import List

from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route, Router

from app.audit import log_audit
from app.db import get_db
from app.models import Script
from app.schemas import (
    MessageResponse,
    ScriptCreate,
    ScriptResponse,
    ScriptUpdate,
)

router = Router()


def _get_db_session() -> Session:
    """Return a database session from dependency factory."""
    return next(get_db())


async def list_scripts(request: Request) -> JSONResponse:
    """Return all stored scripts ordered by name."""
    db: Session = _get_db_session()
    try:
        scripts: List[Script] = db.query(Script).order_by(Script.name.asc()).all()
        payload = [ScriptResponse.model_validate(script).model_dump(mode="json") for script in scripts]
        return JSONResponse(payload)
    finally:
        db.close()


async def create_script(request: Request) -> JSONResponse:
    """Create a new reusable script."""
    db: Session = _get_db_session()
    try:
        data = await request.json()
        script_data = ScriptCreate(**data)

        new_script = Script(
            id=uuid.uuid4(),
            name=script_data.name.strip(),
            language=script_data.language.strip(),
            description=script_data.description.strip() if script_data.description else None,
            content=script_data.content,
            created_by=getattr(request.state, "user", "admin"),
        )
        db.add(new_script)
        db.commit()
        db.refresh(new_script)

        log_audit(
            db,
            user=getattr(request.state, "user", "admin"),
            action="create",
            object_type="script",
            object_id=str(new_script.id),
            meta={"name": new_script.name, "language": new_script.language},
        )

        return JSONResponse(
            ScriptResponse.model_validate(new_script).model_dump(mode="json"),
            status_code=201,
        )
    except Exception as exc:  # pragma: no cover - generic safety net mirrors existing endpoints
        db.rollback()
        return JSONResponse({"error": str(exc)}, status_code=400)
    finally:
        db.close()


async def get_script(request: Request) -> JSONResponse:
    """Fetch a single script by identifier."""
    script_id = request.path_params["script_id"]
    db: Session = _get_db_session()
    try:
        script = db.query(Script).filter(Script.id == script_id).first()
        if not script:
            return JSONResponse({"error": "Script not found"}, status_code=404)
        return JSONResponse(ScriptResponse.model_validate(script).model_dump(mode="json"))
    finally:
        db.close()


async def update_script(request: Request) -> JSONResponse:
    """Update script fields."""
    script_id = request.path_params["script_id"]
    db: Session = _get_db_session()
    try:
        payload = await request.json()
        update_data = ScriptUpdate(**payload)

        script = db.query(Script).filter(Script.id == script_id).first()
        if not script:
            return JSONResponse({"error": "Script not found"}, status_code=404)

        for field, value in update_data.model_dump(exclude_unset=True).items():
            if isinstance(value, str):
                trimmed = value.strip()
                setattr(script, field, trimmed or (None if field == "description" else trimmed))
            else:
                setattr(script, field, value)

        script.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(script)

        log_audit(
            db,
            user=getattr(request.state, "user", "admin"),
            action="update",
            object_type="script",
            object_id=str(script.id),
            meta={"name": script.name, "language": script.language},
        )

        return JSONResponse(ScriptResponse.model_validate(script).model_dump(mode="json"))
    except Exception as exc:  # pragma: no cover - mirrors existing endpoints
        db.rollback()
        return JSONResponse({"error": str(exc)}, status_code=400)
    finally:
        db.close()


async def delete_script(request: Request) -> JSONResponse:
    """Delete a script by identifier."""
    script_id = request.path_params["script_id"]
    db: Session = _get_db_session()
    try:
        script = db.query(Script).filter(Script.id == script_id).first()
        if not script:
            return JSONResponse({"error": "Script not found"}, status_code=404)

        log_audit(
            db,
            user=getattr(request.state, "user", "admin"),
            action="delete",
            object_type="script",
            object_id=str(script.id),
            meta={"name": script.name},
        )

        db.delete(script)
        db.commit()

        return JSONResponse(MessageResponse(message="Script deleted successfully").model_dump())
    finally:
        db.close()


routes = [
    Route("/", list_scripts, methods=["GET"]),
    Route("/", create_script, methods=["POST"]),
    Route("/{script_id:uuid}", get_script, methods=["GET"]),
    Route("/{script_id:uuid}", update_script, methods=["PUT"]),
    Route("/{script_id:uuid}", delete_script, methods=["DELETE"]),
]

scripts_router = Router(routes=routes)
