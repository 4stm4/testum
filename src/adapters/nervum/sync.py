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
from adapters.postgres.orm_models import (
    NervumAddressPoolRow,
    NervumApplyScheduleRow,
    NervumBgpPeerRow,
    NervumEventQuarantineRow,
    NervumFloatingIpRow,
    NervumGatewayBondRow,
    NervumLoadBalancerRow,
    NervumLogicalPortRow,
    NervumMirrorSessionRow,
    NervumNetworkRow,
    NervumNodeRow,
    NervumProjectRow,
    NervumQosPolicyRow,
    NervumRouterRow,
    NervumSecurityGroupRow,
    NervumSecurityPolicyRow,
    NervumServiceObjectRow,
    NervumSyncStateRow,
    NervumTrunkPortRow,
    NervumVpnTunnelRow,
)
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
    eid   = event.get("event_id", 0)
    rtype = event.get("resource_type", "")

    if schema_v > SUPPORTED_SCHEMA_VERSION:
        logger.warning(
            "nervum: unknown schema_version=%d on event_id=%s — quarantined",
            schema_v, eid,
        )
        db.add(NervumEventQuarantineRow(
            event_id=eid,
            schema_version=schema_v,
            event_type=event.get("event_type"),
            resource_type=rtype,
            resource_id=event.get("resource_id"),
            raw=event,
        ))
        db.commit()
        return

    etype   = event.get("event_type", "")
    rid     = event.get("resource_id") or ""
    pid     = event.get("project_id")
    payload = event.get("payload", {})

    _RESOURCE_HANDLERS = {
        "network":         _apply_network_event,
        "node":            _apply_node_event,
        "logical_port":    _apply_logical_port_event,
        "security_group":  _apply_security_group_event,
        "address_pool":    _apply_address_pool_event,
        "service_object":  _apply_service_object_event,
        "qos_policy":      _apply_qos_policy_event,
        "security_policy": _apply_security_policy_event,
        "trunk_port":      _apply_trunk_port_event,
        "router":          _apply_router_event,
        "floating_ip":     _apply_floating_ip_event,
        "bgp_peer":        _apply_bgp_peer_event,
        "gateway_bond":    _apply_gateway_bond_event,
        "load_balancer":   _apply_load_balancer_event,
        "apply_schedule":  _apply_apply_schedule_event,
        "mirror_session":  _apply_mirror_session_event,
        "vpn_tunnel":      _apply_vpn_tunnel_event,
        "project":         _apply_project_event,
    }

    handler = _RESOURCE_HANDLERS.get(rtype)
    if handler:
        handler(db, etype, rid, pid, payload)
    else:
        logger.debug("nervum: unhandled resource_type=%s event_type=%s — ignored", rtype, etype)

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


def _apply_node_event(db, etype: str, rid: str, _pid: str | None, payload: dict) -> None:
    if etype in ("node.registered", "node.enrolled", "node.updated"):
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


def _upsert(db, model, rid: str, project_id: str | None, payload: dict, **extra) -> None:
    """Generic upsert helper for simple replica rows."""
    row = db.query(model).filter(model.id == rid).first()
    if not row:
        row = model(id=rid)
        db.add(row)
    if hasattr(row, "name"):
        row.name = payload.get("name", getattr(row, "name", "") or "")
    if hasattr(row, "project_id"):
        row.project_id = project_id or payload.get("project_id", getattr(row, "project_id", None))
    for attr, key in extra.items():
        setattr(row, attr, payload.get(key, getattr(row, attr, None)))
    if hasattr(row, "labels"):
        row.labels = payload.get("labels", getattr(row, "labels", None))
    row.raw        = payload
    row.updated_at = datetime.utcnow()


def _delete(db, model, rid: str) -> None:
    db.query(model).filter(model.id == rid).delete()


def _apply_logical_port_event(db, etype: str, rid: str, pid: str | None, payload: dict) -> None:
    if etype in ("logical_port.created", "logical_port.updated", "logical_port.status_changed"):
        _upsert(db, NervumLogicalPortRow, rid, pid, payload,
                network_id="network_id", status="status",
                mac="mac", ip_address="ip_address")
    elif etype == "logical_port.deleted":
        _delete(db, NervumLogicalPortRow, rid)


def _apply_security_group_event(db, etype: str, rid: str, pid: str | None, payload: dict) -> None:
    if etype in ("security_group.created", "security_group.updated", "security_group.rules_updated"):
        row = db.query(NervumSecurityGroupRow).filter(NervumSecurityGroupRow.id == rid).first()
        if not row:
            row = NervumSecurityGroupRow(id=rid)
            db.add(row)
        row.name       = payload.get("name", row.name or "")
        row.project_id = pid or payload.get("project_id", row.project_id)
        row.rules      = payload.get("rules", row.rules)
        row.labels     = payload.get("labels", row.labels)
        row.raw        = payload
        row.updated_at = datetime.utcnow()
    elif etype == "security_group.deleted":
        _delete(db, NervumSecurityGroupRow, rid)


def _apply_address_pool_event(db, etype: str, rid: str, pid: str | None, payload: dict) -> None:
    if etype in ("address_pool.created", "address_pool.updated"):
        _upsert(db, NervumAddressPoolRow, rid, pid, payload, cidr="cidr")
    elif etype == "address_pool.deleted":
        _delete(db, NervumAddressPoolRow, rid)


def _apply_service_object_event(db, etype: str, rid: str, pid: str | None, payload: dict) -> None:
    if etype in ("service_object.created", "service_object.updated"):
        _upsert(db, NervumServiceObjectRow, rid, pid, payload,
                protocol="protocol", port_range="port_range")
    elif etype == "service_object.deleted":
        _delete(db, NervumServiceObjectRow, rid)


def _apply_qos_policy_event(db, etype: str, rid: str, pid: str | None, payload: dict) -> None:
    if etype in ("qos_policy.created", "qos_policy.updated"):
        _upsert(db, NervumQosPolicyRow, rid, pid, payload)
    elif etype == "qos_policy.deleted":
        _delete(db, NervumQosPolicyRow, rid)


def _apply_security_policy_event(db, etype: str, rid: str, pid: str | None, payload: dict) -> None:
    if etype in ("security_policy.created", "security_policy.updated",
                 "security_policy.compiled", "security_policy.applied",
                 "security_policy.apply_failed"):
        _upsert(db, NervumSecurityPolicyRow, rid, pid, payload, status="status")
    elif etype == "security_policy.deleted":
        _delete(db, NervumSecurityPolicyRow, rid)


def _apply_trunk_port_event(db, etype: str, rid: str, pid: str | None, payload: dict) -> None:
    if etype in ("trunk_port.created", "trunk_port.updated"):
        _upsert(db, NervumTrunkPortRow, rid, pid, payload)
    elif etype == "trunk_port.deleted":
        _delete(db, NervumTrunkPortRow, rid)


def _apply_router_event(db, etype: str, rid: str, pid: str | None, payload: dict) -> None:
    if etype in ("router.created", "router.updated", "router.status_changed"):
        _upsert(db, NervumRouterRow, rid, pid, payload, status="status", mode="mode")
    elif etype == "router.deleted":
        _delete(db, NervumRouterRow, rid)


def _apply_floating_ip_event(db, etype: str, rid: str, pid: str | None, payload: dict) -> None:
    if etype in ("floating_ip.created", "floating_ip.updated", "floating_ip.status_changed"):
        _upsert(db, NervumFloatingIpRow, rid, pid, payload,
                router_id="router_id", address="address", status="status")
    elif etype == "floating_ip.deleted":
        _delete(db, NervumFloatingIpRow, rid)


def _apply_bgp_peer_event(db, etype: str, rid: str, pid: str | None, payload: dict) -> None:
    if etype in ("bgp_peer.created", "bgp_peer.updated"):
        _upsert(db, NervumBgpPeerRow, rid, pid, payload,
                router_id="router_id", peer_ip="peer_ip", remote_asn="remote_asn")
    elif etype == "bgp_peer.deleted":
        _delete(db, NervumBgpPeerRow, rid)


def _apply_gateway_bond_event(db, etype: str, rid: str, pid: str | None, payload: dict) -> None:
    if etype in ("gateway_bond.created", "gateway_bond.updated"):
        _upsert(db, NervumGatewayBondRow, rid, pid, payload, mode="mode")
    elif etype == "gateway_bond.deleted":
        _delete(db, NervumGatewayBondRow, rid)


def _apply_load_balancer_event(db, etype: str, rid: str, pid: str | None, payload: dict) -> None:
    if etype in ("load_balancer.created", "load_balancer.updated",
                 "load_balancer.status_changed"):
        _upsert(db, NervumLoadBalancerRow, rid, pid, payload,
                router_id="router_id", status="status")
    elif etype == "load_balancer.deleted":
        _delete(db, NervumLoadBalancerRow, rid)


def _apply_apply_schedule_event(db, etype: str, rid: str, pid: str | None, payload: dict) -> None:
    if etype in ("apply_schedule.created", "apply_schedule.updated",
                 "apply_schedule.status_changed"):
        _upsert(db, NervumApplyScheduleRow, rid, pid, payload, status="status")
    elif etype == "apply_schedule.deleted":
        _delete(db, NervumApplyScheduleRow, rid)


def _apply_mirror_session_event(db, etype: str, rid: str, pid: str | None, payload: dict) -> None:
    if etype in ("mirror_session.created", "mirror_session.updated",
                 "mirror_session.status_changed"):
        _upsert(db, NervumMirrorSessionRow, rid, pid, payload, status="status")
    elif etype == "mirror_session.deleted":
        _delete(db, NervumMirrorSessionRow, rid)


def _apply_vpn_tunnel_event(db, etype: str, rid: str, pid: str | None, payload: dict) -> None:
    if etype in ("vpn_tunnel.created", "vpn_tunnel.updated", "vpn_tunnel.status_changed"):
        _upsert(db, NervumVpnTunnelRow, rid, pid, payload, protocol="protocol", status="status")
    elif etype == "vpn_tunnel.deleted":
        _delete(db, NervumVpnTunnelRow, rid)


def _apply_project_event(db, etype: str, rid: str, _pid: str | None, payload: dict) -> None:
    if etype in ("project.created", "project.updated"):
        _upsert(db, NervumProjectRow, rid, None, payload,
                slug="slug", status="status")
    elif etype == "project.deleted":
        _delete(db, NervumProjectRow, rid)


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
