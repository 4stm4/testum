"""Nervum SDN API — replica read/write endpoints + webhook receiver."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route, Router

from adapters.nervum.client import verify_signature
from adapters.nervum.sync import apply_event, _get_or_create_state
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
    SdnTaskRow,
)
from app.config import config
from app.db import SessionLocal
from app.rbac import require_roles, ALL_ROLES

logger = logging.getLogger(__name__)

_seen_delivery_ids: set[str] = set()
_MAX_SEEN = 10_000


# ── CRUD factory helpers ──────────────────────────────────────────────────────

def _ts(row):
    return row.updated_at.isoformat() if row.updated_at else None


def _make_list(RowClass, serialize, *, order_col=None, filter_col="project_id"):
    """Return a GET-list handler that optionally filters by one query param."""
    async def _h(request: Request):
        fval = request.query_params.get(filter_col) if filter_col else None
        with SessionLocal() as db:
            q = db.query(RowClass)
            if order_col is not None:
                q = q.order_by(order_col)
            elif hasattr(RowClass, "name"):
                q = q.order_by(RowClass.name)
            else:
                q = q.order_by(RowClass.id)
            if fval and hasattr(RowClass, filter_col):
                q = q.filter(getattr(RowClass, filter_col) == fval)
            return JSONResponse([serialize(r) for r in q.all()])
    return require_roles(*ALL_ROLES)(_h)


def _make_create(RowClass, build_fn):
    """Return a POST handler; build_fn(body) → ORM row or JSONResponse on error."""
    async def _h(request: Request):
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON"}, status_code=400)
        result = build_fn(body)
        if isinstance(result, JSONResponse):
            return result
        with SessionLocal() as db:
            db.add(result)
            db.commit()
            db.refresh(result)
            return JSONResponse(
                {"id": result.id, "name": getattr(result, "name", result.id)},
                status_code=201,
            )
    return require_roles(*ALL_ROLES)(_h)


def _make_delete(RowClass):
    """Return a DELETE handler that removes a row by path param {id}."""
    async def _h(request: Request):
        rid = request.path_params["id"]
        with SessionLocal() as db:
            row = db.query(RowClass).filter(RowClass.id == rid).first()
            if not row:
                return JSONResponse({"error": "Not found"}, status_code=404)
            db.delete(row)
            db.commit()
        return JSONResponse({"status": "deleted"})
    return require_roles(*ALL_ROLES)(_h)


def _req(body, field):
    """Return stripped string value or None; used for required-field validation."""
    v = (body.get(field) or "").strip()
    return v if v else None


# ── Sync status / trigger ─────────────────────────────────────────────────────

@require_roles(*ALL_ROLES)
async def sync_status(request: Request):
    with SessionLocal() as db:
        state = _get_or_create_state(db)
        counts = {
            "network_count":         db.query(NervumNetworkRow).count(),
            "node_count":            db.query(NervumNodeRow).count(),
            "logical_port_count":    db.query(NervumLogicalPortRow).count(),
            "router_count":          db.query(NervumRouterRow).count(),
            "floating_ip_count":     db.query(NervumFloatingIpRow).count(),
            "security_group_count":  db.query(NervumSecurityGroupRow).count(),
            "security_policy_count": db.query(NervumSecurityPolicyRow).count(),
            "load_balancer_count":   db.query(NervumLoadBalancerRow).count(),
            "vpn_tunnel_count":      db.query(NervumVpnTunnelRow).count(),
            "bgp_peer_count":        db.query(NervumBgpPeerRow).count(),
            "address_pool_count":    db.query(NervumAddressPoolRow).count(),
            "service_object_count":  db.query(NervumServiceObjectRow).count(),
            "qos_policy_count":      db.query(NervumQosPolicyRow).count(),
            "trunk_port_count":      db.query(NervumTrunkPortRow).count(),
            "gateway_bond_count":    db.query(NervumGatewayBondRow).count(),
            "apply_schedule_count":  db.query(NervumApplyScheduleRow).count(),
            "mirror_session_count":  db.query(NervumMirrorSessionRow).count(),
            "project_count":         db.query(NervumProjectRow).count(),
            "quarantine_count":      db.query(NervumEventQuarantineRow).count(),
        }
        return JSONResponse({
            "watermark":            state.watermark,
            "subscription_id":      state.subscription_id,
            "last_synced_at":       state.last_synced_at.isoformat() if state.last_synced_at else None,
            "consecutive_failures": state.consecutive_failures,
            "nervum_url":           config.NERVUM_URL or "",
            "nervum_configured":    bool(config.NERVUM_URL),
            **counts,
        })


@require_roles(*ALL_ROLES)
async def trigger_resync(request: Request):
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


# ── Webhook receiver ──────────────────────────────────────────────────────────

async def webhook_receiver(request: Request):
    """POST /webhooks/nervum — HMAC-validated, no JWT auth (public path)."""
    raw_body = await request.body()

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

    delivery_id = request.headers.get("X-SDN-Delivery-Id", "")
    if delivery_id:
        if delivery_id in _seen_delivery_ids:
            logger.debug("nervum webhook: duplicate delivery_id=%s — ignored", delivery_id)
            return JSONResponse({"status": "duplicate"}, status_code=200)
        _seen_delivery_ids.add(delivery_id)
        if len(_seen_delivery_ids) > _MAX_SEEN:
            _seen_delivery_ids.clear()

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


# ── SDN Tasks (read-only) ─────────────────────────────────────────────────────

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


# ── Networks ──────────────────────────────────────────────────────────────────

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
                "updated_at":     _ts(r),
            }
            for r in rows
        ])


def _build_network(b):
    name = _req(b, "name")
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=422)
    return NervumNetworkRow(
        id=str(uuid.uuid4()),
        name=name,
        type=b.get("type") or None,
        project_id=b.get("project_id") or None,
        vni=int(b["vni"]) if b.get("vni") else None,
        mtu=int(b["mtu"]) if b.get("mtu") else None,
    )

create_network = _make_create(NervumNetworkRow, _build_network)
delete_network  = _make_delete(NervumNetworkRow)


# ── Nodes ─────────────────────────────────────────────────────────────────────

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
                "updated_at":    _ts(r),
            }
            for r in rows
        ])

delete_node = _make_delete(NervumNodeRow)


# ── Logical Ports ─────────────────────────────────────────────────────────────

@require_roles(*ALL_ROLES)
async def list_logical_ports(request: Request):
    project_id = request.query_params.get("project_id")
    network_id = request.query_params.get("network_id")
    with SessionLocal() as db:
        q = db.query(NervumLogicalPortRow).order_by(NervumLogicalPortRow.name)
        if project_id:
            q = q.filter(NervumLogicalPortRow.project_id == project_id)
        if network_id:
            q = q.filter(NervumLogicalPortRow.network_id == network_id)
        rows = q.all()
        return JSONResponse([
            {
                "id":         r.id,
                "name":       r.name,
                "network_id": r.network_id,
                "project_id": r.project_id,
                "status":     r.status,
                "mac":        r.mac,
                "ip_address": r.ip_address,
                "labels":     r.labels or {},
                "updated_at": _ts(r),
            }
            for r in rows
        ])


@require_roles(*ALL_ROLES)
async def get_logical_port(request: Request):
    port_id = request.path_params["port_id"]
    with SessionLocal() as db:
        row = db.query(NervumLogicalPortRow).filter(NervumLogicalPortRow.id == port_id).first()
        if not row:
            return JSONResponse({"error": "Logical port not found"}, status_code=404)
        return JSONResponse({
            "id":         row.id,
            "name":       row.name,
            "network_id": row.network_id,
            "project_id": row.project_id,
            "status":     row.status,
            "mac":        row.mac,
            "ip_address": row.ip_address,
            "labels":     row.labels or {},
            "raw":        row.raw,
            "updated_at": _ts(row),
        })


def _build_port(b):
    name = _req(b, "name")
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=422)
    return NervumLogicalPortRow(
        id=str(uuid.uuid4()),
        name=name,
        network_id=b.get("network_id") or None,
        project_id=b.get("project_id") or None,
        status="pending",
    )

create_port = _make_create(NervumLogicalPortRow, _build_port)
delete_port  = _make_delete(NervumLogicalPortRow)


# ── Routers ───────────────────────────────────────────────────────────────────

@require_roles(*ALL_ROLES)
async def list_sdn_routers(request: Request):
    project_id = request.query_params.get("project_id")
    with SessionLocal() as db:
        q = db.query(NervumRouterRow).order_by(NervumRouterRow.name)
        if project_id:
            q = q.filter(NervumRouterRow.project_id == project_id)
        rows = q.all()
        return JSONResponse([
            {
                "id":         r.id,
                "name":       r.name,
                "project_id": r.project_id,
                "status":     r.status,
                "mode":       r.mode,
                "labels":     r.labels or {},
                "updated_at": _ts(r),
            }
            for r in rows
        ])


def _build_router(b):
    name = _req(b, "name")
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=422)
    return NervumRouterRow(
        id=str(uuid.uuid4()),
        name=name,
        project_id=b.get("project_id") or None,
        mode=b.get("mode") or None,
        status="build",
    )

create_router = _make_create(NervumRouterRow, _build_router)
delete_router  = _make_delete(NervumRouterRow)


# ── Security Groups ───────────────────────────────────────────────────────────

list_security_groups = _make_list(
    NervumSecurityGroupRow,
    lambda r: {"id": r.id, "name": r.name, "project_id": r.project_id,
               "rules": r.rules or [], "updated_at": _ts(r)},
)

def _build_sec_group(b):
    name = _req(b, "name")
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=422)
    return NervumSecurityGroupRow(id=str(uuid.uuid4()), name=name,
                                  project_id=b.get("project_id") or None)

create_security_group = _make_create(NervumSecurityGroupRow, _build_sec_group)
delete_security_group  = _make_delete(NervumSecurityGroupRow)


# ── Floating IPs ──────────────────────────────────────────────────────────────

list_floating_ips = _make_list(
    NervumFloatingIpRow,
    lambda r: {"id": r.id, "address": r.address, "project_id": r.project_id,
               "router_id": r.router_id, "status": r.status, "updated_at": _ts(r)},
    order_col=NervumFloatingIpRow.address,
)

def _build_fip(b):
    return NervumFloatingIpRow(
        id=str(uuid.uuid4()),
        project_id=b.get("project_id") or None,
        router_id=b.get("router_id") or None,
        address=b.get("address") or None,
        status="down",
    )

create_floating_ip = _make_create(NervumFloatingIpRow, _build_fip)
delete_floating_ip  = _make_delete(NervumFloatingIpRow)


# ── VPN Tunnels ───────────────────────────────────────────────────────────────

list_vpn_tunnels = _make_list(
    NervumVpnTunnelRow,
    lambda r: {"id": r.id, "name": r.name, "project_id": r.project_id,
               "protocol": r.protocol, "status": r.status, "updated_at": _ts(r)},
)

def _build_vpn(b):
    name = _req(b, "name")
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=422)
    return NervumVpnTunnelRow(
        id=str(uuid.uuid4()), name=name,
        project_id=b.get("project_id") or None,
        protocol=b.get("protocol") or None,
        status="build",
    )

create_vpn_tunnel = _make_create(NervumVpnTunnelRow, _build_vpn)
delete_vpn_tunnel  = _make_delete(NervumVpnTunnelRow)


# ── Load Balancers ────────────────────────────────────────────────────────────

list_load_balancers = _make_list(
    NervumLoadBalancerRow,
    lambda r: {"id": r.id, "name": r.name, "project_id": r.project_id,
               "router_id": r.router_id, "status": r.status, "updated_at": _ts(r)},
)

def _build_lb(b):
    name = _req(b, "name")
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=422)
    return NervumLoadBalancerRow(
        id=str(uuid.uuid4()), name=name,
        project_id=b.get("project_id") or None,
        router_id=b.get("router_id") or None,
        status="build",
    )

create_load_balancer = _make_create(NervumLoadBalancerRow, _build_lb)
delete_load_balancer  = _make_delete(NervumLoadBalancerRow)


# ── BGP Peers ─────────────────────────────────────────────────────────────────

list_bgp_peers = _make_list(
    NervumBgpPeerRow,
    lambda r: {"id": r.id, "peer_ip": r.peer_ip, "remote_asn": r.remote_asn,
               "router_id": r.router_id, "project_id": r.project_id, "updated_at": _ts(r)},
    order_col=NervumBgpPeerRow.peer_ip,
)

def _build_bgp(b):
    peer_ip = _req(b, "peer_ip")
    if not peer_ip:
        return JSONResponse({"error": "peer_ip is required"}, status_code=422)
    return NervumBgpPeerRow(
        id=str(uuid.uuid4()),
        peer_ip=peer_ip,
        project_id=b.get("project_id") or None,
        router_id=b.get("router_id") or None,
        remote_asn=int(b["remote_asn"]) if b.get("remote_asn") else None,
    )

create_bgp_peer = _make_create(NervumBgpPeerRow, _build_bgp)
delete_bgp_peer  = _make_delete(NervumBgpPeerRow)


# ── Address Pools ─────────────────────────────────────────────────────────────

list_address_pools = _make_list(
    NervumAddressPoolRow,
    lambda r: {"id": r.id, "name": r.name, "project_id": r.project_id,
               "cidr": r.cidr, "updated_at": _ts(r)},
)

def _build_pool(b):
    name = _req(b, "name")
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=422)
    return NervumAddressPoolRow(
        id=str(uuid.uuid4()), name=name,
        project_id=b.get("project_id") or None,
        cidr=b.get("cidr") or None,
    )

create_address_pool = _make_create(NervumAddressPoolRow, _build_pool)
delete_address_pool  = _make_delete(NervumAddressPoolRow)


# ── Service Objects ───────────────────────────────────────────────────────────

list_service_objects = _make_list(
    NervumServiceObjectRow,
    lambda r: {"id": r.id, "name": r.name, "project_id": r.project_id,
               "protocol": r.protocol, "port_range": r.port_range, "updated_at": _ts(r)},
)

def _build_svcobj(b):
    name = _req(b, "name")
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=422)
    return NervumServiceObjectRow(
        id=str(uuid.uuid4()), name=name,
        project_id=b.get("project_id") or None,
        protocol=b.get("protocol") or None,
        port_range=b.get("port_range") or None,
    )

create_service_object = _make_create(NervumServiceObjectRow, _build_svcobj)
delete_service_object  = _make_delete(NervumServiceObjectRow)


# ── QoS Policies ──────────────────────────────────────────────────────────────

list_qos_policies = _make_list(
    NervumQosPolicyRow,
    lambda r: {"id": r.id, "name": r.name, "project_id": r.project_id, "updated_at": _ts(r)},
)

def _build_qos(b):
    name = _req(b, "name")
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=422)
    return NervumQosPolicyRow(id=str(uuid.uuid4()), name=name,
                               project_id=b.get("project_id") or None)

create_qos_policy = _make_create(NervumQosPolicyRow, _build_qos)
delete_qos_policy  = _make_delete(NervumQosPolicyRow)


# ── Security Policies ─────────────────────────────────────────────────────────

list_security_policies = _make_list(
    NervumSecurityPolicyRow,
    lambda r: {"id": r.id, "name": r.name, "project_id": r.project_id,
               "status": r.status, "updated_at": _ts(r)},
)

def _build_secpol(b):
    name = _req(b, "name")
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=422)
    return NervumSecurityPolicyRow(
        id=str(uuid.uuid4()), name=name,
        project_id=b.get("project_id") or None,
        status="draft",
    )

create_security_policy = _make_create(NervumSecurityPolicyRow, _build_secpol)
delete_security_policy  = _make_delete(NervumSecurityPolicyRow)


# ── Trunk Ports ───────────────────────────────────────────────────────────────

list_trunk_ports = _make_list(
    NervumTrunkPortRow,
    lambda r: {"id": r.id, "name": r.name, "project_id": r.project_id, "updated_at": _ts(r)},
)

def _build_trunk(b):
    name = _req(b, "name")
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=422)
    return NervumTrunkPortRow(id=str(uuid.uuid4()), name=name,
                               project_id=b.get("project_id") or None)

create_trunk_port = _make_create(NervumTrunkPortRow, _build_trunk)
delete_trunk_port  = _make_delete(NervumTrunkPortRow)


# ── Gateway Bonds ─────────────────────────────────────────────────────────────

list_gateway_bonds = _make_list(
    NervumGatewayBondRow,
    lambda r: {"id": r.id, "name": r.name, "project_id": r.project_id,
               "mode": r.mode, "updated_at": _ts(r)},
)

def _build_gwbond(b):
    name = _req(b, "name")
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=422)
    return NervumGatewayBondRow(
        id=str(uuid.uuid4()), name=name,
        project_id=b.get("project_id") or None,
        mode=b.get("mode") or None,
    )

create_gateway_bond = _make_create(NervumGatewayBondRow, _build_gwbond)
delete_gateway_bond  = _make_delete(NervumGatewayBondRow)


# ── Apply Schedules ───────────────────────────────────────────────────────────

list_apply_schedules = _make_list(
    NervumApplyScheduleRow,
    lambda r: {"id": r.id, "name": r.name, "project_id": r.project_id,
               "status": r.status, "updated_at": _ts(r)},
)

def _build_sched(b):
    name = _req(b, "name")
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=422)
    return NervumApplyScheduleRow(
        id=str(uuid.uuid4()), name=name,
        project_id=b.get("project_id") or None,
        status="active",
    )

create_apply_schedule = _make_create(NervumApplyScheduleRow, _build_sched)
delete_apply_schedule  = _make_delete(NervumApplyScheduleRow)


# ── Mirror Sessions ───────────────────────────────────────────────────────────

list_mirror_sessions = _make_list(
    NervumMirrorSessionRow,
    lambda r: {"id": r.id, "name": r.name, "project_id": r.project_id,
               "status": r.status, "updated_at": _ts(r)},
)

def _build_mirror(b):
    name = _req(b, "name")
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=422)
    return NervumMirrorSessionRow(
        id=str(uuid.uuid4()), name=name,
        project_id=b.get("project_id") or None,
        status="inactive",
    )

create_mirror_session = _make_create(NervumMirrorSessionRow, _build_mirror)
delete_mirror_session  = _make_delete(NervumMirrorSessionRow)


# ── Router ────────────────────────────────────────────────────────────────────

nervum_router = Router(routes=[
    # Sync
    Route("/sync/status",                   sync_status),
    Route("/sync/trigger",                  trigger_resync,          methods=["POST"]),
    # Networks
    Route("/networks",                      list_networks,           methods=["GET"]),
    Route("/networks",                      create_network,          methods=["POST"]),
    Route("/networks/{id}",                 delete_network,          methods=["DELETE"]),
    # Nodes
    Route("/nodes",                         list_nodes,              methods=["GET"]),
    Route("/nodes/{id}",                    delete_node,             methods=["DELETE"]),
    # Logical Ports
    Route("/logical-ports",                 list_logical_ports,      methods=["GET"]),
    Route("/logical-ports",                 create_port,             methods=["POST"]),
    Route("/logical-ports/{port_id}",       get_logical_port,        methods=["GET"]),
    Route("/logical-ports/{id}",            delete_port,             methods=["DELETE"]),
    # Routers
    Route("/routers",                       list_sdn_routers,        methods=["GET"]),
    Route("/routers",                       create_router,           methods=["POST"]),
    Route("/routers/{id}",                  delete_router,           methods=["DELETE"]),
    # Operations (read-only)
    Route("/operations",                    list_sdn_tasks,          methods=["GET"]),
    Route("/operations/{task_id}",          get_sdn_task),
    # Security Groups
    Route("/security-groups",               list_security_groups,    methods=["GET"]),
    Route("/security-groups",               create_security_group,   methods=["POST"]),
    Route("/security-groups/{id}",          delete_security_group,   methods=["DELETE"]),
    # Floating IPs
    Route("/floating-ips",                  list_floating_ips,       methods=["GET"]),
    Route("/floating-ips",                  create_floating_ip,      methods=["POST"]),
    Route("/floating-ips/{id}",             delete_floating_ip,      methods=["DELETE"]),
    # VPN Tunnels
    Route("/vpn-tunnels",                   list_vpn_tunnels,        methods=["GET"]),
    Route("/vpn-tunnels",                   create_vpn_tunnel,       methods=["POST"]),
    Route("/vpn-tunnels/{id}",              delete_vpn_tunnel,       methods=["DELETE"]),
    # Load Balancers
    Route("/load-balancers",                list_load_balancers,     methods=["GET"]),
    Route("/load-balancers",                create_load_balancer,    methods=["POST"]),
    Route("/load-balancers/{id}",           delete_load_balancer,    methods=["DELETE"]),
    # BGP Peers
    Route("/bgp-peers",                     list_bgp_peers,          methods=["GET"]),
    Route("/bgp-peers",                     create_bgp_peer,         methods=["POST"]),
    Route("/bgp-peers/{id}",                delete_bgp_peer,         methods=["DELETE"]),
    # Address Pools
    Route("/address-pools",                 list_address_pools,      methods=["GET"]),
    Route("/address-pools",                 create_address_pool,     methods=["POST"]),
    Route("/address-pools/{id}",            delete_address_pool,     methods=["DELETE"]),
    # Service Objects
    Route("/service-objects",               list_service_objects,    methods=["GET"]),
    Route("/service-objects",               create_service_object,   methods=["POST"]),
    Route("/service-objects/{id}",          delete_service_object,   methods=["DELETE"]),
    # QoS Policies
    Route("/qos-policies",                  list_qos_policies,       methods=["GET"]),
    Route("/qos-policies",                  create_qos_policy,       methods=["POST"]),
    Route("/qos-policies/{id}",             delete_qos_policy,       methods=["DELETE"]),
    # Security Policies
    Route("/security-policies",             list_security_policies,  methods=["GET"]),
    Route("/security-policies",             create_security_policy,  methods=["POST"]),
    Route("/security-policies/{id}",        delete_security_policy,  methods=["DELETE"]),
    # Trunk Ports
    Route("/trunk-ports",                   list_trunk_ports,        methods=["GET"]),
    Route("/trunk-ports",                   create_trunk_port,       methods=["POST"]),
    Route("/trunk-ports/{id}",              delete_trunk_port,       methods=["DELETE"]),
    # Gateway Bonds
    Route("/gateway-bonds",                 list_gateway_bonds,      methods=["GET"]),
    Route("/gateway-bonds",                 create_gateway_bond,     methods=["POST"]),
    Route("/gateway-bonds/{id}",            delete_gateway_bond,     methods=["DELETE"]),
    # Apply Schedules
    Route("/apply-schedules",               list_apply_schedules,    methods=["GET"]),
    Route("/apply-schedules",               create_apply_schedule,   methods=["POST"]),
    Route("/apply-schedules/{id}",          delete_apply_schedule,   methods=["DELETE"]),
    # Mirror Sessions
    Route("/mirror-sessions",               list_mirror_sessions,    methods=["GET"]),
    Route("/mirror-sessions",               create_mirror_session,   methods=["POST"]),
    Route("/mirror-sessions/{id}",          delete_mirror_session,   methods=["DELETE"]),
])
