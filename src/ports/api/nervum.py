"""Nervum SDN API — replica read endpoints + webhook receiver."""
import json
import logging
from datetime import datetime

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route, Router

from app.config import config
from app.db import SessionLocal
from app.rbac import require_roles, ALL_ROLES
from adapters.postgres.orm_models import NervumNetworkRow, NervumNodeRow, NervumSyncStateRow
from adapters.nervum.client import verify_signature
from adapters.nervum.sync import apply_event, _get_or_create_state

logger = logging.getLogger(__name__)

# Simple in-memory deduplication set (TTL not needed for small window)
_seen_event_ids: set[int] = set()
_MAX_SEEN = 10_000


@require_roles(*ALL_ROLES)
async def list_networks(request: Request):
    with SessionLocal() as db:
        rows = db.query(NervumNetworkRow).order_by(NervumNetworkRow.name).all()
        return JSONResponse([
            {
                "id": r.id,
                "name": r.name,
                "type": r.type,
                "vni": r.vni,
                "vlan_id": r.vlan_id,
                "mtu": r.mtu,
                "intent_version": r.intent_version,
                "spec_hash": r.spec_hash,
                "node_ids": r.node_ids or [],
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ])


@require_roles(*ALL_ROLES)
async def list_nodes(request: Request):
    with SessionLocal() as db:
        rows = db.query(NervumNodeRow).order_by(NervumNodeRow.name).all()
        return JSONResponse([
            {
                "id": r.id,
                "name": r.name,
                "mgmt_ip": r.mgmt_ip,
                "status": r.status,
                "agent_version": r.agent_version,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ])


@require_roles(*ALL_ROLES)
async def sync_status(request: Request):
    with SessionLocal() as db:
        state = _get_or_create_state(db)
        nets = db.query(NervumNetworkRow).count()
        nodes = db.query(NervumNodeRow).count()
        return JSONResponse({
            "watermark": state.watermark,
            "subscription_id": state.subscription_id,
            "last_synced_at": state.last_synced_at.isoformat() if state.last_synced_at else None,
            "consecutive_failures": state.consecutive_failures,
            "network_count": nets,
            "node_count": nodes,
            "nervum_url": config.NERVUM_URL or "",
        })


@require_roles(*ALL_ROLES)
async def trigger_resync(request: Request):
    """Manually trigger a delta recovery from nervum."""
    if not config.NERVUM_URL:
        return JSONResponse({"error": "NERVUM_URL not configured"}, status_code=503)
    from adapters.nervum.client import NervumClient
    from adapters.nervum.sync import recover_delta
    import asyncio
    client = NervumClient()
    try:
        await recover_delta(client)
        return JSONResponse({"message": "Resync complete"})
    except Exception as exc:
        logger.exception("Manual resync failed")
        return JSONResponse({"error": str(exc)}, status_code=500)


async def webhook_receiver(request: Request):
    """Receive nervum webhook events. No auth middleware — HMAC-validated."""
    raw_body = await request.body()

    # HMAC validation
    sig = request.headers.get("X-SDN-Signature", "")
    secret = config.NERVUM_WEBHOOK_SECRET or ""
    if secret:
        if not verify_signature(raw_body, sig, secret):
            logger.warning("nervum webhook: invalid HMAC signature")
            with SessionLocal() as db:
                state = _get_or_create_state(db)
                state.consecutive_failures = (state.consecutive_failures or 0) + 1
                db.commit()
            return JSONResponse({"error": "Invalid signature"}, status_code=401)

    try:
        event = json.loads(raw_body)
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    # Deduplication
    event_id = event.get("event_id") or event.get("id")
    delivery_id = request.headers.get("X-SDN-Delivery-Id", "")
    dedup_key = event_id if event_id is not None else delivery_id
    if dedup_key and dedup_key in _seen_event_ids:
        logger.debug("nervum webhook: duplicate event_id=%s ignored", dedup_key)
        return JSONResponse({"status": "duplicate"}, status_code=200)
    if dedup_key:
        _seen_event_ids.add(dedup_key)
        if len(_seen_event_ids) > _MAX_SEEN:
            # Evict oldest half — simple approach since set has no order, just clear
            _seen_event_ids.clear()

    # Apply event asynchronously (return 200 immediately)
    import asyncio

    async def _apply():
        try:
            with SessionLocal() as db:
                apply_event(db, event)
            with SessionLocal() as db:
                state = _get_or_create_state(db)
                state.consecutive_failures = 0
                db.commit()
        except Exception:
            logger.exception("nervum webhook: failed to apply event %s", event_id)
            with SessionLocal() as db:
                state = _get_or_create_state(db)
                state.consecutive_failures = (state.consecutive_failures or 0) + 1
                db.commit()

    asyncio.create_task(_apply())
    return JSONResponse({"status": "accepted"}, status_code=202)


nervum_router = Router(routes=[
    Route("/networks", list_networks),
    Route("/nodes", list_nodes),
    Route("/sync/status", sync_status),
    Route("/sync/trigger", trigger_resync, methods=["POST"]),
])
