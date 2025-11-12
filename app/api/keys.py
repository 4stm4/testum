"""SSH Keys API endpoints."""
import uuid
from typing import List

from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route, Router

from app import crypto
from app.audit import log_audit
from app.db import get_db
from app.models import SSHKey, UserRole
from app.pagination import get_pagination_params
from app.rbac import ALL_ROLES, get_request_user, require_roles
from app.schemas import MessageResponse, SSHKeyCreate, SSHKeyResponse

router = Router()


@require_roles(*ALL_ROLES)
async def list_keys(request: Request):
    """List all SSH keys."""
    db: Session = next(get_db())
    try:
        try:
            limit, offset = get_pagination_params(request, default_limit=25)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

        query = db.query(SSHKey)
        total = query.count()
        keys: List[SSHKey] = (
            query.order_by(SSHKey.created_at.desc()).offset(offset).limit(limit).all()
        )
        items = []
        for key in keys:
            key_dict = SSHKeyResponse.model_validate(key).model_dump(mode="json")
            key_dict["has_private_key"] = key.encrypted_private_key is not None
            items.append(key_dict)

        response = JSONResponse(items)
        response.headers["X-Total-Count"] = str(total)
        response.headers["X-Limit"] = str(limit)
        response.headers["X-Offset"] = str(offset)
        return response
    finally:
        db.close()


@require_roles(UserRole.ADMIN, UserRole.OPERATOR)
async def create_key(request: Request):
    """Create new SSH key."""
    db: Session = next(get_db())
    try:
        data = await request.json()
        key_data = SSHKeyCreate(**data)

        # Encrypt private key if provided
        encrypted_private_key = None
        if key_data.private_key:
            encrypted_private_key = crypto.encrypt_string(key_data.private_key)

        # Create key
        user = get_request_user(request)
        new_key = SSHKey(
            id=uuid.uuid4(),
            name=key_data.name,
            public_key=key_data.public_key,
            encrypted_private_key=encrypted_private_key,
            created_by=user.username if user else "system",
        )

        db.add(new_key)
        db.commit()
        db.refresh(new_key)

        # Audit log
        log_audit(
            db,
            user=user.username if user else "system",
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


@require_roles(UserRole.ADMIN, UserRole.OPERATOR)
async def delete_key(request: Request):
    """Delete SSH key."""
    key_id = request.path_params["key_id"]
    db: Session = next(get_db())
    try:
        key = db.query(SSHKey).filter(SSHKey.id == key_id).first()
        if not key:
            return JSONResponse({"error": "Key not found"}, status_code=404)

        # Audit log
        user = get_request_user(request)
        log_audit(
            db,
            user=user.username if user else "system",
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
