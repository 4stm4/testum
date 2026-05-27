"""Nervum SDN API — replica read endpoints + webhook receiver."""

from __future__ import annotations

import asyncio
import json
import logging

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route, Router

from adapters.nervum.client import verify_signature
from adapters.nervum.sync import apply_event, _get_or_create_state
from adapters.postgres.orm_models import NervumNetworkRow, NervumNodeRow, NervumSyncStateRow, SdnTaskRow
from app.config import config
from app.db import SessionLocal
from app.rbac import require_roles, ALL_ROLES

logger = logging.getLogger(__name__)

# In-memory dedup set — survives only for the process lifetime.
# After restart, recovery poll fills the gap via watermark so duplicates
# from before the restart are harmless (apply_event is idempotent).
_seen_delivery_ids: set[str] = set()
_MAX_SEEN = 10_000


# ── Read endpoints ────────────────────────────────────────────────────────

@require_roles(*ALL_ROLES)
async def list_networks(request: Request):
    project_id = request.query_params.get("project_id")
    with SessionLocal() as db:
        q = db.query(NervumNetworkRow).order_by(NervumNetworkRow.name)
        if project_id:
            q = q.filter(NervumNetworkRow.project_id == project_id)
        rows = q.all()
        return JSONResponse([
            {
                "id":             r.id,
                "name":           r.name,
                "type":           r.type,
                "project_id":     r.project_id,
                "vni":            r.vni,
                "vlan_id":        r.vlan_id,
                "mtu":            r.mtu,
                "intent_version": r.intent_version,
                "spec_hash":      r.spec_hash,
                "node_ids":       r.node_ids or [],
                "labels":         r.labels or {},
                "updated_at":     r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ])


@require_roles(*ALL_ROLES)
async def list_nodes(request: Request):
    with SessionLocal() as db:
        rows = db.query(NervumNodeRow).order_by(NervumNodeRow.name).all()
        return JSONResponse([
            {
                "id":            r.id,
                "name":          r.name,
                "mgmt_ip":       r.mgmt_ip,
                "status":        r.status,
                "agent_version": r.agent_version,
                "roles":         r.roles or [],
                "labels":        r.labels or {},
                "updated_at":    r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ])


@require_roles(*ALL_ROLES)
async def sync_status(request: Request):
    with SessionLocal() as db:
        state = _get_or_create_state(db)
        nets  = db.query(NervumNetworkRow).count()
        nodes = db.query(NervumNodeRow).count()
        return JSONResponse({
            "watermark":            state.watermark,
            "subscription_id":      state.subscription_id,
            "last_synced_at":       state.last_synced_at.isoformat() if state.last_synced_at else None,
            "consecutive_failures": state.consecutive_failures,
            "network_count":        nets,
            "node_count":           nodes,
            "nervum_url":           config.NERVUM_URL or "",
            "nervum_configured":    bool(config.NERVUM_URL),
        })


@require_roles(*ALL_ROLES)
async def trigger_resync(request: Request):
    """Fire-and-forget delta recovery — returns immediately."""
    if not config.NERVUM_URL:
        return JSONResponse({"error": "NERVUM_URL not configured"}, status_code=503)

    from adapters.nervum.client import NervumClient
    from adapters.nervum.sync import recover_delta

    async def _run():
        try:
            await recover_delta(NervumClient())
        except Exception:
            logger.exception("nervum: manual resync failed")

    asyncio.create_task(_run())
    return JSONResponse({"message": "Resync started"}, status_code=202)


# ── Webhook receiver ──────────────────────────────────────────────────────

async def webhook_receiver(request: Request):
    """POST /webhooks/nervum — HMAC-validated, no JWT auth (public path)."""
    raw_body = await request.body()

    # ── HMAC validation ───────────────────────────────────────────────────
    sig    = request.headers.get("X-SDN-Signature", "")
    secret = config.NERVUM_WEBHOOK_SECRET or ""
    if secret and not verify_signature(raw_body, sig, secret):
        logger.warning("nervum webhook: invalid HMAC — sig=%s", sig[:30])
        with SessionLocal() as db:
            s = _get_or_create_state(db)
            s.consecutive_failures = (s.consecutive_failures or 0) + 1
            db.commit()
        return JSONResponse({"error": "Invalid signature"}, status_code=401)

    try:
        event = json.loads(raw_body)
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    # ── Deduplication on X-SDN-Delivery-Id (per-attempt unique) ──────────
    delivery_id = request.headers.get("X-SDN-Delivery-Id", "")
    if delivery_id:
        if delivery_id in _seen_delivery_ids:
            logger.debug("nervum webhook: duplicate delivery_id=%s — ignored", delivery_id)
            return JSONResponse({"status": "duplicate"}, status_code=200)
        _seen_delivery_ids.add(delivery_id)
        if len(_seen_delivery_ids) > _MAX_SEEN:
            _seen_delivery_ids.clear()

    # ── Async apply (respond ≤5s per contract) ────────────────────────────
    async def _apply():
        try:
            with SessionLocal() as db:
                apply_event(db, event)
            with SessionLocal() as db:
                s = _get_or_create_state(db)
                s.consecutive_failures = 0
                db.commit()
        except Exception:
            eid = event.get("event_id")
            logger.exception("nervum webhook: apply failed event_id=%s", eid)
            with SessionLocal() as db:
                s = _get_or_create_state(db)
                s.consecutive_failures = (s.consecutive_failures or 0) + 1
                db.commit()

    asyncio.create_task(_apply())
    return JSONResponse({"status": "accepted"}, status_code=202)


# ── SDN Tasks (T5 operation bridge) ──────────────────────────────────────

@require_roles(*ALL_ROLES)
async def list_sdn_tasks(request: Request):
    project_id = request.query_params.get("project_id")
    status     = request.query_params.get("status")
    limit      = min(int(request.query_params.get("limit", 50)), 200)
    with SessionLocal() as db:
        q = db.query(SdnTaskRow).order_by(SdnTaskRow.started_at.desc())
        if project_id:
            q = q.filter(SdnTaskRow.project_id == project_id)
        if status:
            q = q.filter(SdnTaskRow.status == status)
        rows = q.limit(limit).all()
        return JSONResponse([
            {
                "id":                  str(r.id),
                "testum_task_id":      r.testum_task_id,
                "nervum_operation_id": r.nervum_operation_id,
                "project_id":          r.project_id,
                "kind":                r.kind,
                "resource_type":       r.resource_type,
                "resource_id":         r.resource_id,
                "status":              r.status,
                "error_code":          r.error_code,
                "error_message":       r.error_message,
                "initiated_by":        r.initiated_by,
                "started_at":          r.started_at.isoformat() if r.started_at else None,
                "finished_at":         r.finished_at.isoformat() if r.finished_at else None,
            }
            for r in rows
        ])


@require_roles(*ALL_ROLES)
async def get_sdn_task(request: Request):
    task_id = request.path_params["task_id"]
    with SessionLocal() as db:
        row = db.query(SdnTaskRow).filter(SdnTaskRow.id == task_id).first()
        if not row:
            return JSONResponse({"error": "SDN task not found"}, status_code=404)
        return JSONResponse({
            "id":                  str(row.id),
            "testum_task_id":      row.testum_task_id,
            "nervum_operation_id": row.nervum_operation_id,
            "project_id":          row.project_id,
            "kind":                row.kind,
            "resource_type":       row.resource_type,
            "resource_id":         row.resource_id,
            "status":              row.status,
            "error_code":          row.error_code,
            "error_message":       row.error_message,
            "initiated_by":        row.initiated_by,
            "started_at":          row.started_at.isoformat() if row.started_at else None,
            "finished_at":         row.finished_at.isoformat() if row.finished_at else None,
            "updated_at":          row.updated_at.isoformat() if row.updated_at else None,
        })


# ── Router ────────────────────────────────────────────────────────────────

nervum_router = Router(routes=[
    Route("/networks",          list_networks),
    Route("/nodes",             list_nodes),
    Route("/sync/status",       sync_status),
    Route("/sync/trigger",      trigger_resync,  methods=["POST"]),
    Route("/operations",        list_sdn_tasks),
    Route("/operations/{task_id}", get_sdn_task),
])
