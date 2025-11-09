"""SSH Keys API endpoints."""
import uuid
from typing import List
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Router, Route
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import SSHKey
from app.schemas import SSHKeyCreate, SSHKeyResponse, MessageResponse
from app.audit import log_audit

router = Router()


async def list_keys(request: Request):
    """List all SSH keys."""
    db: Session = next(get_db())
    try:
        keys = db.query(SSHKey).all()
        return JSONResponse([SSHKeyResponse.model_validate(key).model_dump(mode="json") for key in keys])
    finally:
        db.close()


async def create_key(request: Request):
    """Create new SSH key."""
    db: Session = next(get_db())
    try:
        data = await request.json()
        key_data = SSHKeyCreate(**data)

        # Create key
        new_key = SSHKey(
            id=uuid.uuid4(),
            name=key_data.name,
            public_key=key_data.public_key,
            created_by=request.state.user if hasattr(request.state, "user") else "admin",
        )

        db.add(new_key)
        db.commit()
        db.refresh(new_key)

        # Audit log
        log_audit(
            db,
            user=request.state.user if hasattr(request.state, "user") else "admin",
            action="create",
            object_type="ssh_key",
            object_id=str(new_key.id),
            meta={"name": new_key.name},
        )

        return JSONResponse(
            SSHKeyResponse.model_validate(new_key).model_dump(mode="json"),
            status_code=201,
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    finally:
        db.close()


async def delete_key(request: Request):
    """Delete SSH key."""
    key_id = request.path_params["key_id"]
    db: Session = next(get_db())
    try:
        key = db.query(SSHKey).filter(SSHKey.id == key_id).first()
        if not key:
            return JSONResponse({"error": "Key not found"}, status_code=404)

        # Audit log
        log_audit(
            db,
            user=request.state.user if hasattr(request.state, "user") else "admin",
            action="delete",
            object_type="ssh_key",
            object_id=str(key.id),
            meta={"name": key.name},
        )

        db.delete(key)
        db.commit()

        return JSONResponse({"message": f"Key {key.name} deleted successfully"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    finally:
        db.close()


# Routes
routes = [
    Route("/", list_keys, methods=["GET"]),
    Route("/", create_key, methods=["POST"]),
    Route("/{key_id:uuid}", delete_key, methods=["DELETE"]),
]

keys_router = Router(routes=routes)
