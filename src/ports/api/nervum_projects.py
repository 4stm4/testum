"""Nervum project binding API — T2: Testum project ↔ Nervum project mapping."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route, Router

from adapters.postgres.orm_models import NervumProjectBindingRow
from app.audit import log_audit
from app.db import SessionLocal
from app.rbac import require_roles, ALL_ROLES, UserRole
from app.rbac import get_request_user

logger = logging.getLogger(__name__)


def _binding_dict(b: NervumProjectBindingRow) -> dict:
    return {
        "id":                  str(b.id),
        "testum_project_id":   b.testum_project_id,
        "nervum_project_id":   b.nervum_project_id,
        "nervum_project_slug": b.nervum_project_slug,
        "status":              b.status,
        "last_sync_at":        b.last_sync_at.isoformat() if b.last_sync_at else None,
        "created_at":          b.created_at.isoformat() if b.created_at else None,
    }


@require_roles(*ALL_ROLES)
async def list_bindings(request: Request):
    with SessionLocal() as db:
        rows = db.query(NervumProjectBindingRow).order_by(
            NervumProjectBindingRow.created_at.desc()
        ).all()
        return JSONResponse([_binding_dict(r) for r in rows])


@require_roles(UserRole.ADMIN, UserRole.OPERATOR)
async def create_binding(request: Request):
    """POST /api/sdn/projects — bind a Testum project to a Nervum project.

    Idempotent: if testum_project_id already bound, returns the existing binding.
    """
    data = await request.json()
    testum_pid  = (data.get("testum_project_id") or "").strip()
    nervum_pid  = (data.get("nervum_project_id") or "").strip()
    nervum_slug = (data.get("nervum_project_slug") or "").strip() or None

    if not testum_pid or not nervum_pid:
        return JSONResponse(
            {"error": "testum_project_id and nervum_project_id are required"},
            status_code=400,
        )

    user = get_request_user(request)

    with SessionLocal() as db:
        existing = (
            db.query(NervumProjectBindingRow)
            .filter(NervumProjectBindingRow.testum_project_id == testum_pid)
            .first()
        )
        if existing:
            return JSONResponse(_binding_dict(existing))

        row = NervumProjectBindingRow(
            id=uuid.uuid4(),
            testum_project_id=testum_pid,
            nervum_project_id=nervum_pid,
            nervum_project_slug=nervum_slug,
            status="active",
        )
        db.add(row)
        db.commit()
        db.refresh(row)

        log_audit(
            db,
            user=user.username if user else "system",
            action="create",
            object_type="nervum_project_binding",
            object_id=str(row.id),
            meta={"testum_project_id": testum_pid, "nervum_project_id": nervum_pid},
        )
        return JSONResponse(_binding_dict(row), status_code=201)


@require_roles(*ALL_ROLES)
async def get_binding(request: Request):
    bid = request.path_params["binding_id"]
    with SessionLocal() as db:
        row = db.query(NervumProjectBindingRow).filter(
            NervumProjectBindingRow.id == bid
        ).first()
        if not row:
            return JSONResponse({"error": "Binding not found"}, status_code=404)
        return JSONResponse(_binding_dict(row))


@require_roles(UserRole.ADMIN)
async def delete_binding(request: Request):
    bid = request.path_params["binding_id"]
    user = get_request_user(request)
    with SessionLocal() as db:
        row = db.query(NervumProjectBindingRow).filter(
            NervumProjectBindingRow.id == bid
        ).first()
        if not row:
            return JSONResponse({"error": "Binding not found"}, status_code=404)
        log_audit(
            db,
            user=user.username if user else "system",
            action="delete",
            object_type="nervum_project_binding",
            object_id=str(row.id),
            meta={"testum_project_id": row.testum_project_id},
        )
        db.delete(row)
        db.commit()
        return JSONResponse({"message": "Binding deleted"})


def resolve_nervum_project(testum_project_id: str) -> str | None:
    """Return the Nervum project_id bound to a Testum project, or None."""
    with SessionLocal() as db:
        row = (
            db.query(NervumProjectBindingRow)
            .filter(
                NervumProjectBindingRow.testum_project_id == testum_project_id,
                NervumProjectBindingRow.status == "active",
            )
            .first()
        )
        return row.nervum_project_id if row else None


project_bindings_router = Router(routes=[
    Route("/",        list_bindings,  methods=["GET"]),
    Route("/",        create_binding, methods=["POST"]),
    Route("/{binding_id}", get_binding,    methods=["GET"]),
    Route("/{binding_id}", delete_binding, methods=["DELETE"]),
])
