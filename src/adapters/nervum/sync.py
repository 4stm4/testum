"""Bootstrap, live-sync, and recovery logic for Nervum replica tables.

Sync flow (from docs/nervum-contract.md):
  cold-start: GET /events/snapshot → populate tables, record watermark
  live:        webhook → HMAC verify → apply_event
  recovery:    GET /events?since=<watermark> until head_event_id reached
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from adapters.nervum.client import NervumClient, SUPPORTED_SCHEMA_VERSION
from adapters.postgres.orm_models import NervumNetworkRow, NervumNodeRow, NervumSyncStateRow
from app.config import config
from app.db import SessionLocal

logger = logging.getLogger(__name__)

RECOVERY_POLL_INTERVAL = 30    # seconds between recovery polls
MAX_FAILURES_BEFORE_RESUB = 10


# ── State singleton ───────────────────────────────────────────────────────

def _get_or_create_state(db) -> NervumSyncStateRow:
    state = db.query(NervumSyncStateRow).filter(NervumSyncStateRow.id == 1).first()
    if not state:
        state = NervumSyncStateRow(id=1, watermark=0, consecutive_failures=0)
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


# ── Event application ─────────────────────────────────────────────────────

def apply_event(db, event: dict) -> None:
    """Update replica tables from a single Nervum outbox event envelope.

    Envelope fields (schema_version=2):
        event_id, id, event_type, resource_type, resource_id,
        schema_version, project_id, occurred_at, payload
    """
    schema_v = event.get("schema_version", 1)
    if schema_v > SUPPORTED_SCHEMA_VERSION:
        logger.warning(
            "nervum: unknown schema_version=%d on event_id=%s — skipping (quarantine)",
            schema_v, event.get("event_id"),
        )
        return

    etype = event.get("event_type", "")
    rtype = event.get("resource_type", "")
    rid   = event.get("resource_id") or ""
    pid   = event.get("project_id")
    payload = event.get("payload", {})
    eid = event.get("event_id", 0)

    if rtype == "network":
        _apply_network_event(db, etype, rid, pid, payload)
    elif rtype == "node":
        _apply_node_event(db, etype, rid, payload)

    # Advance watermark
    state = _get_or_create_state(db)
    if eid > state.watermark:
        state.watermark = eid
        state.last_synced_at = datetime.utcnow()
    db.commit()


def _apply_network_event(db, etype: str, rid: str, project_id: str | None, payload: dict) -> None:
    if etype in ("network.created", "network.updated", "network.nodes_assigned"):
        row = db.query(NervumNetworkRow).filter(NervumNetworkRow.id == rid).first()
        if not row:
            row = NervumNetworkRow(id=rid)
            db.add(row)
        row.name           = payload.get("name", row.name or "")
        row.type           = payload.get("type", row.type)
        row.project_id     = project_id or payload.get("project_id", row.project_id)
        row.intent_version = payload.get("intent_version", row.intent_version)
        row.spec_hash      = payload.get("spec_hash", row.spec_hash)
        row.node_ids       = payload.get("node_ids", row.node_ids)
        row.labels         = payload.get("labels", row.labels)
        row.raw            = payload
        row.updated_at     = datetime.utcnow()

    elif etype in ("network.applied", "network.apply_failed"):
        row = db.query(NervumNetworkRow).filter(NervumNetworkRow.id == rid).first()
        if row:
            row.intent_version = payload.get("intent_version", row.intent_version)
            row.spec_hash      = payload.get("spec_hash", row.spec_hash)
            row.raw            = {**(row.raw or {}), **payload}
            row.updated_at     = datetime.utcnow()


def _apply_node_event(db, etype: str, rid: str, payload: dict) -> None:
    if etype in ("node.registered", "node.enrolled"):
        row = db.query(NervumNodeRow).filter(NervumNodeRow.id == rid).first()
        if not row:
            row = NervumNodeRow(id=rid)
            db.add(row)
        row.name          = payload.get("name", row.name or "")
        row.mgmt_ip       = payload.get("mgmt_ip", row.mgmt_ip)
        row.status        = payload.get("status", row.status)
        row.agent_version = payload.get("agent_version", row.agent_version)
        row.roles         = payload.get("roles", row.roles)
        row.labels        = payload.get("labels", row.labels)
        row.raw           = payload
        row.updated_at    = datetime.utcnow()

    elif etype == "node.removed":
        db.query(NervumNodeRow).filter(NervumNodeRow.id == rid).delete()


# ── Bootstrap ─────────────────────────────────────────────────────────────

async def bootstrap(client: NervumClient) -> None:
    """Load full snapshot and populate replica tables (cold-start)."""
    logger.info("nervum: starting bootstrap snapshot")
    data = await client.get_snapshot()
    # data: {event_id: int, networks: [...], nodes: [...]}

    with SessionLocal() as db:
        state = _get_or_create_state(db)

        for net in data.get("networks", []):
            rid = net.get("id", "")
            if not rid:
                continue
            row = db.query(NervumNetworkRow).filter(NervumNetworkRow.id == rid).first()
            if not row:
                row = NervumNetworkRow(id=rid)
                db.add(row)
            row.name           = net.get("name", "")
            row.type           = net.get("type")
            row.project_id     = net.get("project_id")
            row.vni            = net.get("vni")
            row.vlan_id        = net.get("vlan_id")
            row.mtu            = net.get("mtu")
            row.intent_version = net.get("intent_version")
            row.spec_hash      = net.get("spec_hash")
            row.node_ids       = net.get("node_ids")
            row.labels         = net.get("labels")
            row.raw            = net
            row.updated_at     = datetime.utcnow()

        for node in data.get("nodes", []):
            rid = node.get("id", "")
            if not rid:
                continue
            row = db.query(NervumNodeRow).filter(NervumNodeRow.id == rid).first()
            if not row:
                row = NervumNodeRow(id=rid)
                db.add(row)
            row.name          = node.get("name", "")
            row.mgmt_ip       = node.get("mgmt_ip")
            row.status        = node.get("status")
            row.agent_version = node.get("agent_version")
            row.roles         = node.get("roles")
            row.labels        = node.get("labels")
            row.raw           = node
            row.updated_at    = datetime.utcnow()

        watermark = data.get("event_id", 0)
        if watermark > state.watermark:
            state.watermark = watermark
        state.last_synced_at = datetime.utcnow()
        db.commit()

    logger.info("nervum: bootstrap complete, watermark=%s", watermark)


# ── Recovery ──────────────────────────────────────────────────────────────

async def recover_delta(client: NervumClient) -> None:
    """Poll /events?since=<watermark> to catch up after downtime."""
    with SessionLocal() as db:
        since = _get_or_create_state(db).watermark

    logger.info("nervum: recovery poll since event_id=%s", since)

    while True:
        page = await client.get_events(since=since, limit=200)
        # Response: {head_event_id: int, items: [...]}  ← NOT a bare list
        items = page.get("items", [])
        head  = page.get("head_event_id", since)

        if not items:
            break

        with SessionLocal() as db:
            for ev in items:
                apply_event(db, ev)
            since = _get_or_create_state(db).watermark

        if since >= head:
            break  # caught up to head

    logger.info("nervum: recovery complete, watermark=%s", since)


# ── Webhook subscription ──────────────────────────────────────────────────

async def ensure_webhook_subscription(client: NervumClient) -> None:
    """Register webhook subscription if NERVUM_CALLBACK_URL is configured."""
    if not config.NERVUM_URL:
        return

    callback_url = config.NERVUM_CALLBACK_URL or ""
    if not callback_url:
        logger.warning("nervum: NERVUM_CALLBACK_URL not set — webhook registration skipped")
        return

    resp = await client.register_webhook(callback_url)
    # Response: {subscription: {id, state, ...}, secret_plaintext: "..."}
    sub = resp.get("subscription", {})
    sub_id = sub.get("id", "")
    secret = resp.get("secret_plaintext", "")

    with SessionLocal() as db:
        state = _get_or_create_state(db)
        state.subscription_id = sub_id
        db.commit()

    if secret:
        logger.info(
            "nervum: webhook registered id=%s — set NERVUM_WEBHOOK_SECRET to the secret_plaintext",
            sub_id,
        )
    else:
        logger.info("nervum: webhook registered id=%s", sub_id)


# ── Main sync loop ────────────────────────────────────────────────────────

async def run_sync_loop() -> None:
    """Background task: bootstrap → subscribe → periodic recovery."""
    if not config.NERVUM_URL:
        logger.info("nervum: NERVUM_URL not set — sync disabled")
        return

    client = NervumClient()

    try:
        await bootstrap(client)
    except Exception:
        logger.exception("nervum: bootstrap failed")

    try:
        await ensure_webhook_subscription(client)
    except Exception:
        logger.exception("nervum: webhook subscription failed (will retry)")

    while True:
        await asyncio.sleep(RECOVERY_POLL_INTERVAL)
        try:
            await recover_delta(client)
        except Exception:
            logger.exception("nervum: recovery poll failed")

        with SessionLocal() as db:
            failures = (_get_or_create_state(db).consecutive_failures or 0)

        if failures >= MAX_FAILURES_BEFORE_RESUB:
            logger.warning("nervum: %d consecutive failures — resubscribing webhook", failures)
            try:
                await ensure_webhook_subscription(client)
                with SessionLocal() as db:
                    s = _get_or_create_state(db)
                    s.consecutive_failures = 0
                    db.commit()
            except Exception:
                logger.exception("nervum: resubscription failed")
