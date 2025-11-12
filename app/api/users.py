"""User management API endpoints with RBAC enforcement."""
import logging
import uuid
from datetime import datetime
from typing import List

from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route, Router

from app.db import get_db
from app.models import User, UserRole
from app.pagination import get_pagination_params
from app.rbac import ALL_ROLES, get_request_user, require_roles
from app.schemas import UserCreate, UserResponse, UserUpdate
from app.security import hash_password

logger = logging.getLogger(__name__)


def _get_db() -> Session:
    return next(get_db())


@require_roles(UserRole.ADMIN)
async def list_users(request: Request) -> JSONResponse:
    """Return a paginated list of users."""

    db = _get_db()
    try:
        try:
            limit, offset = get_pagination_params(request, default_limit=25, max_limit=200)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

        query = db.query(User)
        total = query.count()
        users: List[User] = (
            query.order_by(User.created_at.desc()).offset(offset).limit(limit).all()
        )
        items = [
            UserResponse.model_validate(user).model_dump(mode="json")
            for user in users
        ]
        response = JSONResponse({
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
        })
        response.headers["X-Total-Count"] = str(total)
        return response
    finally:
        db.close()


@require_roles(UserRole.ADMIN)
async def create_user(request: Request) -> JSONResponse:
    """Create a new user."""

    db = _get_db()
    try:
        payload = await request.json()
        user_data = UserCreate(**payload)

        username = user_data.username.strip()
        if db.query(User).filter(User.username == username).first():
            return JSONResponse({"error": "Username already exists"}, status_code=409)

        if user_data.email and db.query(User).filter(User.email == user_data.email).first():
            return JSONResponse({"error": "Email already exists"}, status_code=409)

        user = User(
            id=uuid.uuid4(),
            username=username,
            email=user_data.email,
            hashed_password=hash_password(user_data.password),
            role=UserRole(user_data.role),
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        logger.info("Created user '%s' with role '%s'", user.username, user.role.value)
        return JSONResponse(
            UserResponse.model_validate(user).model_dump(mode="json"),
            status_code=201,
        )
    finally:
        db.close()


@require_roles(*ALL_ROLES)
async def get_current_user(request: Request) -> JSONResponse:
    """Return the authenticated user's profile."""

    user_context = get_request_user(request)
    if not user_context:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    db = _get_db()
    try:
        user = db.query(User).filter(User.id == user_context.id).first()
        if not user:
            return JSONResponse({"error": "User not found"}, status_code=404)
        return JSONResponse(UserResponse.model_validate(user).model_dump(mode="json"))
    finally:
        db.close()


@require_roles(UserRole.ADMIN)
async def get_user(request: Request) -> JSONResponse:
    """Return a user by identifier."""

    user_id = request.path_params["user_id"]
    db = _get_db()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return JSONResponse({"error": "User not found"}, status_code=404)
        return JSONResponse(UserResponse.model_validate(user).model_dump(mode="json"))
    finally:
        db.close()


@require_roles(UserRole.ADMIN)
async def update_user(request: Request) -> JSONResponse:
    """Update user properties."""

    user_id = request.path_params["user_id"]
    db = _get_db()
    try:
        payload = await request.json()
        update_data = UserUpdate(**payload)

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return JSONResponse({"error": "User not found"}, status_code=404)

        if update_data.username:
            username = update_data.username.strip()
            if (
                db.query(User)
                .filter(User.username == username, User.id != user.id)
                .first()
            ):
                return JSONResponse({"error": "Username already exists"}, status_code=409)
            user.username = username

        if update_data.email is not None:
            if (
                update_data.email
                and db.query(User)
                .filter(User.email == update_data.email, User.id != user.id)
                .first()
            ):
                return JSONResponse({"error": "Email already exists"}, status_code=409)
            user.email = update_data.email

        if update_data.password:
            user.hashed_password = hash_password(update_data.password)

        if update_data.role:
            user.role = UserRole(update_data.role)

        if update_data.is_active is not None:
            if not update_data.is_active and str(user.id) == get_request_user(request).id:
                return JSONResponse({"error": "Cannot deactivate yourself"}, status_code=400)
            user.is_active = update_data.is_active

        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)

        return JSONResponse(UserResponse.model_validate(user).model_dump(mode="json"))
    finally:
        db.close()


@require_roles(UserRole.ADMIN)
async def delete_user(request: Request) -> JSONResponse:
    """Remove a user."""

    user_id = request.path_params["user_id"]
    user_context = get_request_user(request)

    if user_context and user_context.id == str(user_id):
        return JSONResponse({"error": "Cannot delete yourself"}, status_code=400)

    db = _get_db()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return JSONResponse({"error": "User not found"}, status_code=404)

        db.delete(user)
        db.commit()
        return JSONResponse({"message": "User deleted"})
    finally:
        db.close()


routes = [
    Route("/", list_users, methods=["GET"]),
    Route("/", create_user, methods=["POST"]),
    Route("/me", get_current_user, methods=["GET"]),
    Route("/{user_id:uuid}", get_user, methods=["GET"]),
    Route("/{user_id:uuid}", update_user, methods=["PUT"]),
    Route("/{user_id:uuid}", delete_user, methods=["DELETE"]),
]

users_router = Router(routes=routes)
