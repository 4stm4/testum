"""Bootstrap, live-sync, and recovery logic for nervum replica tables."""
import asyncio
import logging
from datetime import datetime

from app.config import config
from app.db import SessionLocal
from adapters.postgres.orm_models import NervumNetworkRow, NervumNodeRow, NervumSyncStateRow
from adapters.nervum.client import NervumClient

logger = logging.getLogger(__name__)

RECOVERY_POLL_INTERVAL = 30   # seconds between recovery polls
MAX_FAILURES_BEFORE_RESUB = 10


def _get_or_create_state(db) -> NervumSyncStateRow:
    state = db.query(NervumSyncStateRow).filter(NervumSyncStateRow.id == 1).first()
    if not state:
        state = NervumSyncStateRow(id=1, watermark=0, consecutive_failures=0)
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


def apply_event(db, event: dict) -> None:
    """Update replica tables based on a single nervum event envelope."""
    etype = event.get("event_type", "")
    rtype = event.get("resource_type", "")
    rid = event.get("resource_id", "")
    payload = event.get("payload", {})
    eid = event.get("event_id", 0)

    if rtype == "network":
        if etype == "network.created" or etype == "network.updated" or etype == "network.nodes_assigned":
            row = db.query(NervumNetworkRow).filter(NervumNetworkRow.id == rid).first()
            if not row:
                row = NervumNetworkRow(id=rid)
                db.add(row)
            row.name = payload.get("name", row.name or "")
            row.type = payload.get("type", row.type)
            row.intent_version = payload.get("intent_version", row.intent_version)
            row.spec_hash = payload.get("spec_hash", row.spec_hash)
            row.node_ids = payload.get("node_ids", row.node_ids)
            row.raw = payload
            row.updated_at = datetime.utcnow()

        elif etype in ("network.applied", "network.apply_failed"):
            row = db.query(NervumNetworkRow).filter(NervumNetworkRow.id == rid).first()
            if row:
                row.intent_version = payload.get("intent_version", row.intent_version)
                row.spec_hash = payload.get("spec_hash", row.spec_hash)
                row.raw = {**(row.raw or {}), **payload}
                row.updated_at = datetime.utcnow()

    elif rtype == "node":
        if etype in ("node.registered", "node.enrolled"):
            row = db.query(NervumNodeRow).filter(NervumNodeRow.id == rid).first()
            if not row:
                row = NervumNodeRow(id=rid)
                db.add(row)
            row.name = payload.get("name", row.name or "")
            row.mgmt_ip = payload.get("mgmt_ip", row.mgmt_ip)
            row.status = payload.get("status", row.status)
            row.agent_version = payload.get("agent_version", row.agent_version)
            row.raw = payload
            row.updated_at = datetime.utcnow()

        elif etype == "node.removed":
            db.query(NervumNodeRow).filter(NervumNodeRow.id == rid).delete()

    # advance watermark
    state = _get_or_create_state(db)
    if eid > state.watermark:
        state.watermark = eid
        state.last_synced_at = datetime.utcnow()

    db.commit()


async def bootstrap(client: NervumClient) -> None:
    """Load full snapshot from nervum and populate replica tables."""
    logger.info("nervum: starting bootstrap snapshot")
    data = await client.get_snapshot()

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
            row.name = net.get("name", "")
            row.type = net.get("type")
            row.vni = net.get("vni")
            row.vlan_id = net.get("vlan_id")
            row.mtu = net.get("mtu")
            row.intent_version = net.get("intent_version")
            row.spec_hash = net.get("spec_hash")
            row.node_ids = net.get("node_ids")
            row.raw = net
            row.updated_at = datetime.utcnow()

        for node in data.get("nodes", []):
            rid = node.get("id", "")
            if not rid:
                continue
            row = db.query(NervumNodeRow).filter(NervumNodeRow.id == rid).first()
            if not row:
                row = NervumNodeRow(id=rid)
                db.add(row)
            row.name = node.get("name", "")
            row.mgmt_ip = node.get("mgmt_ip")
            row.status = node.get("status")
            row.agent_version = node.get("agent_version")
            row.raw = node
            row.updated_at = datetime.utcnow()

        watermark = data.get("event_id", data.get("watermark", 0))
        if watermark > state.watermark:
            state.watermark = watermark
        state.last_synced_at = datetime.utcnow()
        db.commit()

    logger.info("nervum: bootstrap complete, watermark=%s", watermark)


async def recover_delta(client: NervumClient) -> None:
    """Poll /events?since=watermark to catch up after a gap."""
    with SessionLocal() as db:
        state = _get_or_create_state(db)
        since = state.watermark

    logger.info("nervum: recovery poll since event_id=%s", since)
    while True:
        events = await client.get_events(since=since, limit=200)
        if not events:
            break
        with SessionLocal() as db:
            for ev in events:
                apply_event(db, ev)
            state = _get_or_create_state(db)
            since = state.watermark
        if len(events) < 200:
            break
    logger.info("nervum: recovery complete, watermark=%s", since)


async def ensure_webhook_subscription(client: NervumClient) -> None:
    """Register or re-register webhook subscription if needed."""
    if not config.NERVUM_URL:
        return

    # Derive callback URL from config or default
    # The actual public URL must be configured via env — use NERVUM_CALLBACK_URL if set
    callback_url = getattr(config, "NERVUM_CALLBACK_URL", None) or ""
    if not callback_url:
        logger.warning("nervum: NERVUM_CALLBACK_URL not set, skipping webhook registration")
        return

    sub = await client.register_webhook(callback_url)
    sub_id = sub.get("subscription_id") or sub.get("id", "")
    secret = sub.get("secret", "")

    with SessionLocal() as db:
        state = _get_or_create_state(db)
        state.subscription_id = sub_id
        db.commit()

    if secret:
        logger.info(
            "nervum: webhook registered id=%s — store secret in NERVUM_WEBHOOK_SECRET", sub_id
        )
    else:
        logger.info("nervum: webhook registered id=%s", sub_id)


async def run_sync_loop() -> None:
    """Background task: bootstrap then run periodic recovery."""
    if not config.NERVUM_URL:
        logger.info("nervum: NERVUM_URL not set — sync disabled")
        return

    client = NervumClient()

    # Cold start: snapshot first, then subscribe
    try:
        await bootstrap(client)
    except Exception:
        logger.exception("nervum: bootstrap failed")

    try:
        await ensure_webhook_subscription(client)
    except Exception:
        logger.exception("nervum: webhook subscription failed (will retry in loop)")

    # Recovery loop: runs every RECOVERY_POLL_INTERVAL seconds
    while True:
        await asyncio.sleep(RECOVERY_POLL_INTERVAL)
        try:
            await recover_delta(client)
        except Exception:
            logger.exception("nervum: recovery poll failed")

        # Check if we need to resubscribe
        with SessionLocal() as db:
            state = _get_or_create_state(db)
            failures = state.consecutive_failures or 0

        if failures >= MAX_FAILURES_BEFORE_RESUB:
            logger.warning("nervum: %d consecutive webhook failures, resubscribing", failures)
            try:
                await ensure_webhook_subscription(client)
                with SessionLocal() as db:
                    state = _get_or_create_state(db)
                    state.consecutive_failures = 0
                    db.commit()
            except Exception:
                logger.exception("nervum: resubscription failed")
