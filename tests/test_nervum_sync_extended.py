# SPDX-License-Identifier: MIT
"""Extended apply_event tests for Nervum resource types not covered in test_nervum_unit.py.

Covered here: security_group, floating_ip, vpn_tunnel, load_balancer, bgp_peer,
address_pool, service_object, qos_policy, security_policy, trunk_port,
gateway_bond, apply_schedule, mirror_session, project.

NOT covered here (already in test_nervum_unit.py): network, node, logical_port, router.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import os

import pytest


# ── fixtures & helpers ────────────────────────────────────────────────────

@pytest.fixture()
def sqlite_db(tmp_path):
    os.environ.setdefault("FERNET_KEY", "XvgfcADXX1oKcITCS8V7iQWr9VcweqQR7H3Vc_2qsFs=")
    os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from adapters.postgres.session import Base
    import adapters.postgres.orm_models  # noqa: F401 — register all models
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    yield db
    db.close()


def _event(resource_type, event_type, resource_id, event_id=1, project_id="p1", payload=None):
    return {
        "schema_version": 2,
        "event_id": event_id,
        "event_type": event_type,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "project_id": project_id,
        "occurred_at": "2026-01-01T00:00:00Z",
        "payload": payload or {},
    }


# ── security_group ────────────────────────────────────────────────────────

def test_apply_event_security_group_created(sqlite_db):
    from adapters.nervum.sync import apply_event
    from adapters.postgres.orm_models import NervumSecurityGroupRow

    ev = _event("security_group", "security_group.created", "sg-1",
                payload={"name": "web-sg", "rules": [{"port": 80}]})
    apply_event(sqlite_db, ev)

    row = sqlite_db.query(NervumSecurityGroupRow).filter_by(id="sg-1").first()
    assert row is not None
    assert row.name == "web-sg"
    assert row.project_id == "p1"
    assert row.rules == [{"port": 80}]


def test_apply_event_security_group_deleted(sqlite_db):
    from adapters.nervum.sync import apply_event
    from adapters.postgres.orm_models import NervumSecurityGroupRow

    apply_event(sqlite_db, _event("security_group", "security_group.created", "sg-2",
                                   event_id=1, payload={"name": "old-sg"}))
    assert sqlite_db.query(NervumSecurityGroupRow).filter_by(id="sg-2").count() == 1

    apply_event(sqlite_db, _event("security_group", "security_group.deleted", "sg-2", event_id=2))
    assert sqlite_db.query(NervumSecurityGroupRow).filter_by(id="sg-2").count() == 0


# ── floating_ip ───────────────────────────────────────────────────────────

def test_apply_event_floating_ip_created(sqlite_db):
    from adapters.nervum.sync import apply_event
    from adapters.postgres.orm_models import NervumFloatingIpRow

    ev = _event("floating_ip", "floating_ip.created", "fip-1",
                payload={"name": "fip-web", "address": "203.0.113.5", "status": "active",
                         "router_id": "r-1"})
    apply_event(sqlite_db, ev)

    row = sqlite_db.query(NervumFloatingIpRow).filter_by(id="fip-1").first()
    assert row is not None
    assert row.address == "203.0.113.5"
    assert row.status == "active"
    assert row.router_id == "r-1"


def test_apply_event_floating_ip_deleted(sqlite_db):
    from adapters.nervum.sync import apply_event
    from adapters.postgres.orm_models import NervumFloatingIpRow

    apply_event(sqlite_db, _event("floating_ip", "floating_ip.created", "fip-2",
                                   event_id=1, payload={"name": "fip-old"}))
    apply_event(sqlite_db, _event("floating_ip", "floating_ip.deleted", "fip-2", event_id=2))
    assert sqlite_db.query(NervumFloatingIpRow).filter_by(id="fip-2").count() == 0


# ── vpn_tunnel ────────────────────────────────────────────────────────────

def test_apply_event_vpn_tunnel_created(sqlite_db):
    from adapters.nervum.sync import apply_event
    from adapters.postgres.orm_models import NervumVpnTunnelRow

    ev = _event("vpn_tunnel", "vpn_tunnel.created", "vpn-1",
                payload={"name": "office-vpn", "protocol": "ipsec", "status": "up"})
    apply_event(sqlite_db, ev)

    row = sqlite_db.query(NervumVpnTunnelRow).filter_by(id="vpn-1").first()
    assert row is not None
    assert row.name == "office-vpn"
    assert row.protocol == "ipsec"
    assert row.status == "up"


def test_apply_event_vpn_tunnel_deleted(sqlite_db):
    from adapters.nervum.sync import apply_event
    from adapters.postgres.orm_models import NervumVpnTunnelRow

    apply_event(sqlite_db, _event("vpn_tunnel", "vpn_tunnel.created", "vpn-2",
                                   event_id=1, payload={"name": "old-vpn"}))
    apply_event(sqlite_db, _event("vpn_tunnel", "vpn_tunnel.deleted", "vpn-2", event_id=2))
    assert sqlite_db.query(NervumVpnTunnelRow).filter_by(id="vpn-2").count() == 0


# ── load_balancer ─────────────────────────────────────────────────────────

def test_apply_event_load_balancer_created(sqlite_db):
    from adapters.nervum.sync import apply_event
    from adapters.postgres.orm_models import NervumLoadBalancerRow

    ev = _event("load_balancer", "load_balancer.created", "lb-1",
                payload={"name": "web-lb", "router_id": "r-1", "status": "active"})
    apply_event(sqlite_db, ev)

    row = sqlite_db.query(NervumLoadBalancerRow).filter_by(id="lb-1").first()
    assert row is not None
    assert row.name == "web-lb"
    assert row.router_id == "r-1"
    assert row.status == "active"


def test_apply_event_load_balancer_deleted(sqlite_db):
    from adapters.nervum.sync import apply_event
    from adapters.postgres.orm_models import NervumLoadBalancerRow

    apply_event(sqlite_db, _event("load_balancer", "load_balancer.created", "lb-2",
                                   event_id=1, payload={"name": "old-lb"}))
    apply_event(sqlite_db, _event("load_balancer", "load_balancer.deleted", "lb-2", event_id=2))
    assert sqlite_db.query(NervumLoadBalancerRow).filter_by(id="lb-2").count() == 0


# ── bgp_peer ──────────────────────────────────────────────────────────────

def test_apply_event_bgp_peer_created(sqlite_db):
    from adapters.nervum.sync import apply_event
    from adapters.postgres.orm_models import NervumBgpPeerRow

    ev = _event("bgp_peer", "bgp_peer.created", "bgp-1",
                payload={"name": "peer-1", "router_id": "r-1",
                         "peer_ip": "10.0.0.1", "remote_asn": 65001})
    apply_event(sqlite_db, ev)

    row = sqlite_db.query(NervumBgpPeerRow).filter_by(id="bgp-1").first()
    assert row is not None
    assert row.peer_ip == "10.0.0.1"
    assert row.remote_asn == 65001
    assert row.router_id == "r-1"


def test_apply_event_bgp_peer_deleted(sqlite_db):
    from adapters.nervum.sync import apply_event
    from adapters.postgres.orm_models import NervumBgpPeerRow

    apply_event(sqlite_db, _event("bgp_peer", "bgp_peer.created", "bgp-2",
                                   event_id=1, payload={"name": "old-peer"}))
    apply_event(sqlite_db, _event("bgp_peer", "bgp_peer.deleted", "bgp-2", event_id=2))
    assert sqlite_db.query(NervumBgpPeerRow).filter_by(id="bgp-2").count() == 0


# ── address_pool ──────────────────────────────────────────────────────────

def test_apply_event_address_pool_created(sqlite_db):
    from adapters.nervum.sync import apply_event
    from adapters.postgres.orm_models import NervumAddressPoolRow

    ev = _event("address_pool", "address_pool.created", "pool-1",
                payload={"name": "mgmt-pool", "cidr": "10.10.0.0/24"})
    apply_event(sqlite_db, ev)

    row = sqlite_db.query(NervumAddressPoolRow).filter_by(id="pool-1").first()
    assert row is not None
    assert row.name == "mgmt-pool"
    assert row.cidr == "10.10.0.0/24"


def test_apply_event_address_pool_deleted(sqlite_db):
    from adapters.nervum.sync import apply_event
    from adapters.postgres.orm_models import NervumAddressPoolRow

    apply_event(sqlite_db, _event("address_pool", "address_pool.created", "pool-2",
                                   event_id=1, payload={"name": "old-pool"}))
    apply_event(sqlite_db, _event("address_pool", "address_pool.deleted", "pool-2", event_id=2))
    assert sqlite_db.query(NervumAddressPoolRow).filter_by(id="pool-2").count() == 0


# ── service_object ────────────────────────────────────────────────────────

def test_apply_event_service_object_created(sqlite_db):
    from adapters.nervum.sync import apply_event
    from adapters.postgres.orm_models import NervumServiceObjectRow

    ev = _event("service_object", "service_object.created", "svc-1",
                payload={"name": "http", "protocol": "tcp", "port_range": "80-80"})
    apply_event(sqlite_db, ev)

    row = sqlite_db.query(NervumServiceObjectRow).filter_by(id="svc-1").first()
    assert row is not None
    assert row.name == "http"
    assert row.protocol == "tcp"
    assert row.port_range == "80-80"


def test_apply_event_service_object_deleted(sqlite_db):
    from adapters.nervum.sync import apply_event
    from adapters.postgres.orm_models import NervumServiceObjectRow

    apply_event(sqlite_db, _event("service_object", "service_object.created", "svc-2",
                                   event_id=1, payload={"name": "old-svc"}))
    apply_event(sqlite_db, _event("service_object", "service_object.deleted", "svc-2",
                                   event_id=2))
    assert sqlite_db.query(NervumServiceObjectRow).filter_by(id="svc-2").count() == 0


# ── qos_policy ────────────────────────────────────────────────────────────

def test_apply_event_qos_policy_created(sqlite_db):
    from adapters.nervum.sync import apply_event
    from adapters.postgres.orm_models import NervumQosPolicyRow

    ev = _event("qos_policy", "qos_policy.created", "qos-1",
                payload={"name": "gold-qos"})
    apply_event(sqlite_db, ev)

    row = sqlite_db.query(NervumQosPolicyRow).filter_by(id="qos-1").first()
    assert row is not None
    assert row.name == "gold-qos"
    assert row.project_id == "p1"


def test_apply_event_qos_policy_deleted(sqlite_db):
    from adapters.nervum.sync import apply_event
    from adapters.postgres.orm_models import NervumQosPolicyRow

    apply_event(sqlite_db, _event("qos_policy", "qos_policy.created", "qos-2",
                                   event_id=1, payload={"name": "old-qos"}))
    apply_event(sqlite_db, _event("qos_policy", "qos_policy.deleted", "qos-2", event_id=2))
    assert sqlite_db.query(NervumQosPolicyRow).filter_by(id="qos-2").count() == 0


# ── security_policy ───────────────────────────────────────────────────────

def test_apply_event_security_policy_created(sqlite_db):
    from adapters.nervum.sync import apply_event
    from adapters.postgres.orm_models import NervumSecurityPolicyRow

    ev = _event("security_policy", "security_policy.created", "sp-1",
                payload={"name": "default-deny", "status": "active"})
    apply_event(sqlite_db, ev)

    row = sqlite_db.query(NervumSecurityPolicyRow).filter_by(id="sp-1").first()
    assert row is not None
    assert row.name == "default-deny"
    assert row.status == "active"


def test_apply_event_security_policy_deleted(sqlite_db):
    from adapters.nervum.sync import apply_event
    from adapters.postgres.orm_models import NervumSecurityPolicyRow

    apply_event(sqlite_db, _event("security_policy", "security_policy.created", "sp-2",
                                   event_id=1, payload={"name": "old-sp"}))
    apply_event(sqlite_db, _event("security_policy", "security_policy.deleted", "sp-2",
                                   event_id=2))
    assert sqlite_db.query(NervumSecurityPolicyRow).filter_by(id="sp-2").count() == 0


# ── trunk_port ────────────────────────────────────────────────────────────

def test_apply_event_trunk_port_created(sqlite_db):
    from adapters.nervum.sync import apply_event
    from adapters.postgres.orm_models import NervumTrunkPortRow

    ev = _event("trunk_port", "trunk_port.created", "trunk-1",
                payload={"name": "vm-trunk"})
    apply_event(sqlite_db, ev)

    row = sqlite_db.query(NervumTrunkPortRow).filter_by(id="trunk-1").first()
    assert row is not None
    assert row.name == "vm-trunk"
    assert row.project_id == "p1"


def test_apply_event_trunk_port_deleted(sqlite_db):
    from adapters.nervum.sync import apply_event
    from adapters.postgres.orm_models import NervumTrunkPortRow

    apply_event(sqlite_db, _event("trunk_port", "trunk_port.created", "trunk-2",
                                   event_id=1, payload={"name": "old-trunk"}))
    apply_event(sqlite_db, _event("trunk_port", "trunk_port.deleted", "trunk-2", event_id=2))
    assert sqlite_db.query(NervumTrunkPortRow).filter_by(id="trunk-2").count() == 0


# ── gateway_bond ──────────────────────────────────────────────────────────

def test_apply_event_gateway_bond_created(sqlite_db):
    from adapters.nervum.sync import apply_event
    from adapters.postgres.orm_models import NervumGatewayBondRow

    ev = _event("gateway_bond", "gateway_bond.created", "gbond-1",
                payload={"name": "bond0", "mode": "active-backup"})
    apply_event(sqlite_db, ev)

    row = sqlite_db.query(NervumGatewayBondRow).filter_by(id="gbond-1").first()
    assert row is not None
    assert row.name == "bond0"
    assert row.mode == "active-backup"


def test_apply_event_gateway_bond_deleted(sqlite_db):
    from adapters.nervum.sync import apply_event
    from adapters.postgres.orm_models import NervumGatewayBondRow

    apply_event(sqlite_db, _event("gateway_bond", "gateway_bond.created", "gbond-2",
                                   event_id=1, payload={"name": "old-bond"}))
    apply_event(sqlite_db, _event("gateway_bond", "gateway_bond.deleted", "gbond-2", event_id=2))
    assert sqlite_db.query(NervumGatewayBondRow).filter_by(id="gbond-2").count() == 0


# ── apply_schedule ────────────────────────────────────────────────────────

def test_apply_event_apply_schedule_created(sqlite_db):
    from adapters.nervum.sync import apply_event
    from adapters.postgres.orm_models import NervumApplyScheduleRow

    ev = _event("apply_schedule", "apply_schedule.created", "sched-1",
                payload={"name": "nightly", "status": "pending"})
    apply_event(sqlite_db, ev)

    row = sqlite_db.query(NervumApplyScheduleRow).filter_by(id="sched-1").first()
    assert row is not None
    assert row.name == "nightly"
    assert row.status == "pending"
    assert row.project_id == "p1"


def test_apply_event_apply_schedule_deleted(sqlite_db):
    from adapters.nervum.sync import apply_event
    from adapters.postgres.orm_models import NervumApplyScheduleRow

    apply_event(sqlite_db, _event("apply_schedule", "apply_schedule.created", "sched-2",
                                   event_id=1, payload={"name": "old-sched"}))
    apply_event(sqlite_db, _event("apply_schedule", "apply_schedule.deleted", "sched-2",
                                   event_id=2))
    assert sqlite_db.query(NervumApplyScheduleRow).filter_by(id="sched-2").count() == 0


# ── mirror_session ────────────────────────────────────────────────────────

def test_apply_event_mirror_session_created(sqlite_db):
    from adapters.nervum.sync import apply_event
    from adapters.postgres.orm_models import NervumMirrorSessionRow

    ev = _event("mirror_session", "mirror_session.created", "mirror-1",
                payload={"name": "capture-web", "status": "active"})
    apply_event(sqlite_db, ev)

    row = sqlite_db.query(NervumMirrorSessionRow).filter_by(id="mirror-1").first()
    assert row is not None
    assert row.name == "capture-web"
    assert row.status == "active"
    assert row.project_id == "p1"


def test_apply_event_mirror_session_deleted(sqlite_db):
    from adapters.nervum.sync import apply_event
    from adapters.postgres.orm_models import NervumMirrorSessionRow

    apply_event(sqlite_db, _event("mirror_session", "mirror_session.created", "mirror-2",
                                   event_id=1, payload={"name": "old-mirror"}))
    apply_event(sqlite_db, _event("mirror_session", "mirror_session.deleted", "mirror-2",
                                   event_id=2))
    assert sqlite_db.query(NervumMirrorSessionRow).filter_by(id="mirror-2").count() == 0


# ── project ───────────────────────────────────────────────────────────────

def test_apply_event_project_created(sqlite_db):
    from adapters.nervum.sync import apply_event
    from adapters.postgres.orm_models import NervumProjectRow

    ev = _event("project", "project.created", "proj-1",
                payload={"name": "acme", "slug": "acme", "status": "active"})
    apply_event(sqlite_db, ev)

    row = sqlite_db.query(NervumProjectRow).filter_by(id="proj-1").first()
    assert row is not None
    assert row.name == "acme"
    assert row.slug == "acme"
    assert row.status == "active"


def test_apply_event_project_deleted(sqlite_db):
    from adapters.nervum.sync import apply_event
    from adapters.postgres.orm_models import NervumProjectRow

    apply_event(sqlite_db, _event("project", "project.created", "proj-2",
                                   event_id=1, payload={"name": "old-proj"}))
    apply_event(sqlite_db, _event("project", "project.deleted", "proj-2", event_id=2))
    assert sqlite_db.query(NervumProjectRow).filter_by(id="proj-2").count() == 0


def test_apply_event_project_synced(sqlite_db):
    """project.synced is NOT a standard create/update event; no row should be created
    unless the handler explicitly handles it.  The important invariant is no crash."""
    from adapters.nervum.sync import apply_event
    from adapters.postgres.orm_models import NervumProjectRow

    ev = _event("project", "project.synced", "proj-synced",
                payload={"name": "synced-proj", "slug": "synced", "status": "active"})
    # Must not raise
    apply_event(sqlite_db, ev)
    # project.synced is not in the handler's accepted list, so no row is created
    assert sqlite_db.query(NervumProjectRow).filter_by(id="proj-synced").count() == 0


# ── cross-cutting ─────────────────────────────────────────────────────────

def test_apply_event_unknown_resource_type_is_noop(sqlite_db):
    """Unknown resource_type must not crash and must not insert any row."""
    from adapters.nervum.sync import apply_event
    from adapters.postgres.orm_models import NervumNetworkRow

    ev = _event("totally_unknown_thing", "totally_unknown_thing.created", "x-1",
                payload={"name": "ghost"})
    # must not raise
    apply_event(sqlite_db, ev)

    # watermark still advances
    from adapters.nervum.sync import _get_or_create_state
    state = _get_or_create_state(sqlite_db)
    assert state.watermark == 1
