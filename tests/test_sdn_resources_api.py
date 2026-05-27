# SPDX-License-Identifier: MIT
"""Integration tests for the 13 SDN resource CRUD endpoints."""
from __future__ import annotations

import uuid

import pytest
from starlette.testclient import TestClient


# ── Helper ────────────────────────────────────────────────────────────────────

def _get(client: TestClient, url: str):
    """GET url; if 404 retry with trailing slash (Starlette Mount behaviour)."""
    r = client.get(url)
    if r.status_code == 404:
        sep = "" if url.endswith("/") else "/"
        r = client.get(url + sep)
    return r


def _post(client: TestClient, url: str, **kwargs):
    r = client.post(url, **kwargs)
    if r.status_code == 404:
        sep = "" if url.endswith("/") else "/"
        r = client.post(url + sep, **kwargs)
    return r


def _delete(client: TestClient, url: str):
    r = client.delete(url)
    if r.status_code == 405:
        # Some Starlette mounts need the trailing slash variant
        sep = "" if url.endswith("/") else "/"
        r = client.delete(url + sep)
    return r


# ══════════════════════════════════════════════════════════════════════════════
# security_groups   /api/sdn/security-groups
# ══════════════════════════════════════════════════════════════════════════════

_SG = "/api/sdn/security-groups"


def test_security_groups_list_empty(client: TestClient):
    r = _get(client, _SG)
    assert r.status_code == 200
    assert r.json() == []


def test_security_groups_create(client: TestClient):
    r = _post(client, _SG, json={"name": "sg-test"})
    assert r.status_code == 201
    data = r.json()
    assert "id" in data
    assert data["name"] == "sg-test"


def test_security_groups_delete(client: TestClient):
    r = _post(client, _SG, json={"name": "sg-del"})
    assert r.status_code == 201
    rid = r.json()["id"]
    rd = _delete(client, f"{_SG}/{rid}")
    assert rd.status_code == 200
    assert rd.json()["status"] == "deleted"


def test_security_groups_delete_not_found(client: TestClient):
    rd = _delete(client, f"{_SG}/{uuid.uuid4()}")
    assert rd.status_code == 404


def test_security_groups_create_missing_required_field(client: TestClient):
    r = _post(client, _SG, json={})
    assert r.status_code == 422


def test_security_groups_create_with_rules(client: TestClient):
    rules = [{"direction": "ingress", "protocol": "tcp", "port": 80}]
    r = _post(client, _SG, json={"name": "sg-with-rules", "rules": rules})
    assert r.status_code == 201
    assert "id" in r.json()


# ══════════════════════════════════════════════════════════════════════════════
# floating_ips   /api/sdn/floating-ips
# ══════════════════════════════════════════════════════════════════════════════

_FIP = "/api/sdn/floating-ips"


def test_floating_ips_list_empty(client: TestClient):
    r = _get(client, _FIP)
    assert r.status_code == 200
    assert r.json() == []


def test_floating_ips_create(client: TestClient):
    r = _post(client, _FIP, json={"address": "203.0.113.1"})
    assert r.status_code == 201
    data = r.json()
    assert "id" in data


def test_floating_ips_delete(client: TestClient):
    r = _post(client, _FIP, json={"address": "203.0.113.2"})
    assert r.status_code == 201
    rid = r.json()["id"]
    rd = _delete(client, f"{_FIP}/{rid}")
    assert rd.status_code == 200
    assert rd.json()["status"] == "deleted"


def test_floating_ips_delete_not_found(client: TestClient):
    rd = _delete(client, f"{_FIP}/{uuid.uuid4()}")
    assert rd.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# vpn_tunnels   /api/sdn/vpn-tunnels
# ══════════════════════════════════════════════════════════════════════════════

_VPN = "/api/sdn/vpn-tunnels"


def test_vpn_tunnels_list_empty(client: TestClient):
    r = _get(client, _VPN)
    assert r.status_code == 200
    assert r.json() == []


def test_vpn_tunnels_create(client: TestClient):
    r = _post(client, _VPN, json={"name": "vpn-test"})
    assert r.status_code == 201
    data = r.json()
    assert "id" in data
    assert data["name"] == "vpn-test"


def test_vpn_tunnels_delete(client: TestClient):
    r = _post(client, _VPN, json={"name": "vpn-del"})
    assert r.status_code == 201
    rid = r.json()["id"]
    rd = _delete(client, f"{_VPN}/{rid}")
    assert rd.status_code == 200
    assert rd.json()["status"] == "deleted"


def test_vpn_tunnels_delete_not_found(client: TestClient):
    rd = _delete(client, f"{_VPN}/{uuid.uuid4()}")
    assert rd.status_code == 404


def test_vpn_tunnels_create_missing_required_field(client: TestClient):
    r = _post(client, _VPN, json={})
    assert r.status_code == 422


def test_vpn_tunnels_create_with_protocol(client: TestClient):
    r = _post(client, _VPN, json={"name": "vpn-wg", "protocol": "wireguard"})
    assert r.status_code == 201
    assert "id" in r.json()


# ══════════════════════════════════════════════════════════════════════════════
# load_balancers   /api/sdn/load-balancers
# ══════════════════════════════════════════════════════════════════════════════

_LB = "/api/sdn/load-balancers"


def test_load_balancers_list_empty(client: TestClient):
    r = _get(client, _LB)
    assert r.status_code == 200
    assert r.json() == []


def test_load_balancers_create(client: TestClient):
    r = _post(client, _LB, json={"name": "lb-test"})
    assert r.status_code == 201
    data = r.json()
    assert "id" in data
    assert data["name"] == "lb-test"


def test_load_balancers_delete(client: TestClient):
    r = _post(client, _LB, json={"name": "lb-del"})
    assert r.status_code == 201
    rid = r.json()["id"]
    rd = _delete(client, f"{_LB}/{rid}")
    assert rd.status_code == 200
    assert rd.json()["status"] == "deleted"


def test_load_balancers_delete_not_found(client: TestClient):
    rd = _delete(client, f"{_LB}/{uuid.uuid4()}")
    assert rd.status_code == 404


def test_load_balancers_create_missing_required_field(client: TestClient):
    r = _post(client, _LB, json={})
    assert r.status_code == 422


# ══════════════════════════════════════════════════════════════════════════════
# bgp_peers   /api/sdn/bgp-peers
# ══════════════════════════════════════════════════════════════════════════════

_BGP = "/api/sdn/bgp-peers"


def test_bgp_peers_list_empty(client: TestClient):
    r = _get(client, _BGP)
    assert r.status_code == 200
    assert r.json() == []


def test_bgp_peers_create(client: TestClient):
    r = _post(client, _BGP, json={"peer_ip": "192.0.2.1"})
    assert r.status_code == 201
    data = r.json()
    assert "id" in data


def test_bgp_peers_delete(client: TestClient):
    r = _post(client, _BGP, json={"peer_ip": "192.0.2.2"})
    assert r.status_code == 201
    rid = r.json()["id"]
    rd = _delete(client, f"{_BGP}/{rid}")
    assert rd.status_code == 200
    assert rd.json()["status"] == "deleted"


def test_bgp_peers_delete_not_found(client: TestClient):
    rd = _delete(client, f"{_BGP}/{uuid.uuid4()}")
    assert rd.status_code == 404


def test_bgp_peers_create_missing_required_field(client: TestClient):
    r = _post(client, _BGP, json={})
    assert r.status_code == 422


def test_bgp_peers_create_with_asn(client: TestClient):
    r = _post(client, _BGP, json={"peer_ip": "192.0.2.3", "remote_asn": 65001})
    assert r.status_code == 201
    assert "id" in r.json()


# ══════════════════════════════════════════════════════════════════════════════
# address_pools   /api/sdn/address-pools
# ══════════════════════════════════════════════════════════════════════════════

_AP = "/api/sdn/address-pools"


def test_address_pools_list_empty(client: TestClient):
    r = _get(client, _AP)
    assert r.status_code == 200
    assert r.json() == []


def test_address_pools_create(client: TestClient):
    r = _post(client, _AP, json={"name": "pool-test", "cidr": "10.100.0.0/24"})
    assert r.status_code == 201
    data = r.json()
    assert "id" in data
    assert data["name"] == "pool-test"


def test_address_pools_delete(client: TestClient):
    r = _post(client, _AP, json={"name": "pool-del"})
    assert r.status_code == 201
    rid = r.json()["id"]
    rd = _delete(client, f"{_AP}/{rid}")
    assert rd.status_code == 200
    assert rd.json()["status"] == "deleted"


def test_address_pools_delete_not_found(client: TestClient):
    rd = _delete(client, f"{_AP}/{uuid.uuid4()}")
    assert rd.status_code == 404


def test_address_pools_create_missing_required_field(client: TestClient):
    r = _post(client, _AP, json={})
    assert r.status_code == 422


# ══════════════════════════════════════════════════════════════════════════════
# service_objects   /api/sdn/service-objects
# ══════════════════════════════════════════════════════════════════════════════

_SO = "/api/sdn/service-objects"


def test_service_objects_list_empty(client: TestClient):
    r = _get(client, _SO)
    assert r.status_code == 200
    assert r.json() == []


def test_service_objects_create(client: TestClient):
    r = _post(client, _SO, json={"name": "svc-http", "protocol": "tcp", "port_range": "80"})
    assert r.status_code == 201
    data = r.json()
    assert "id" in data
    assert data["name"] == "svc-http"


def test_service_objects_delete(client: TestClient):
    r = _post(client, _SO, json={"name": "svc-del"})
    assert r.status_code == 201
    rid = r.json()["id"]
    rd = _delete(client, f"{_SO}/{rid}")
    assert rd.status_code == 200
    assert rd.json()["status"] == "deleted"


def test_service_objects_delete_not_found(client: TestClient):
    rd = _delete(client, f"{_SO}/{uuid.uuid4()}")
    assert rd.status_code == 404


def test_service_objects_create_missing_required_field(client: TestClient):
    r = _post(client, _SO, json={})
    assert r.status_code == 422


# ══════════════════════════════════════════════════════════════════════════════
# qos_policies   /api/sdn/qos-policies
# ══════════════════════════════════════════════════════════════════════════════

_QOS = "/api/sdn/qos-policies"


def test_qos_policies_list_empty(client: TestClient):
    r = _get(client, _QOS)
    assert r.status_code == 200
    assert r.json() == []


def test_qos_policies_create(client: TestClient):
    r = _post(client, _QOS, json={"name": "qos-test"})
    assert r.status_code == 201
    data = r.json()
    assert "id" in data
    assert data["name"] == "qos-test"


def test_qos_policies_delete(client: TestClient):
    r = _post(client, _QOS, json={"name": "qos-del"})
    assert r.status_code == 201
    rid = r.json()["id"]
    rd = _delete(client, f"{_QOS}/{rid}")
    assert rd.status_code == 200
    assert rd.json()["status"] == "deleted"


def test_qos_policies_delete_not_found(client: TestClient):
    rd = _delete(client, f"{_QOS}/{uuid.uuid4()}")
    assert rd.status_code == 404


def test_qos_policies_create_missing_required_field(client: TestClient):
    r = _post(client, _QOS, json={})
    assert r.status_code == 422


# ══════════════════════════════════════════════════════════════════════════════
# security_policies   /api/sdn/security-policies
# ══════════════════════════════════════════════════════════════════════════════

_SP = "/api/sdn/security-policies"


def test_security_policies_list_empty(client: TestClient):
    r = _get(client, _SP)
    assert r.status_code == 200
    assert r.json() == []


def test_security_policies_create(client: TestClient):
    r = _post(client, _SP, json={"name": "secpol-test"})
    assert r.status_code == 201
    data = r.json()
    assert "id" in data
    assert data["name"] == "secpol-test"


def test_security_policies_delete(client: TestClient):
    r = _post(client, _SP, json={"name": "secpol-del"})
    assert r.status_code == 201
    rid = r.json()["id"]
    rd = _delete(client, f"{_SP}/{rid}")
    assert rd.status_code == 200
    assert rd.json()["status"] == "deleted"


def test_security_policies_delete_not_found(client: TestClient):
    rd = _delete(client, f"{_SP}/{uuid.uuid4()}")
    assert rd.status_code == 404


def test_security_policies_create_missing_required_field(client: TestClient):
    r = _post(client, _SP, json={})
    assert r.status_code == 422


# ══════════════════════════════════════════════════════════════════════════════
# trunk_ports   /api/sdn/trunk-ports
# ══════════════════════════════════════════════════════════════════════════════

_TP = "/api/sdn/trunk-ports"


def test_trunk_ports_list_empty(client: TestClient):
    r = _get(client, _TP)
    assert r.status_code == 200
    assert r.json() == []


def test_trunk_ports_create(client: TestClient):
    r = _post(client, _TP, json={"name": "trunk-test"})
    assert r.status_code == 201
    data = r.json()
    assert "id" in data
    assert data["name"] == "trunk-test"


def test_trunk_ports_delete(client: TestClient):
    r = _post(client, _TP, json={"name": "trunk-del"})
    assert r.status_code == 201
    rid = r.json()["id"]
    rd = _delete(client, f"{_TP}/{rid}")
    assert rd.status_code == 200
    assert rd.json()["status"] == "deleted"


def test_trunk_ports_delete_not_found(client: TestClient):
    rd = _delete(client, f"{_TP}/{uuid.uuid4()}")
    assert rd.status_code == 404


def test_trunk_ports_create_missing_required_field(client: TestClient):
    r = _post(client, _TP, json={})
    assert r.status_code == 422


# ══════════════════════════════════════════════════════════════════════════════
# gateway_bonds   /api/sdn/gateway-bonds
# ══════════════════════════════════════════════════════════════════════════════

_GB = "/api/sdn/gateway-bonds"


def test_gateway_bonds_list_empty(client: TestClient):
    r = _get(client, _GB)
    assert r.status_code == 200
    assert r.json() == []


def test_gateway_bonds_create(client: TestClient):
    r = _post(client, _GB, json={"name": "bond-test"})
    assert r.status_code == 201
    data = r.json()
    assert "id" in data
    assert data["name"] == "bond-test"


def test_gateway_bonds_delete(client: TestClient):
    r = _post(client, _GB, json={"name": "bond-del"})
    assert r.status_code == 201
    rid = r.json()["id"]
    rd = _delete(client, f"{_GB}/{rid}")
    assert rd.status_code == 200
    assert rd.json()["status"] == "deleted"


def test_gateway_bonds_delete_not_found(client: TestClient):
    rd = _delete(client, f"{_GB}/{uuid.uuid4()}")
    assert rd.status_code == 404


def test_gateway_bonds_create_missing_required_field(client: TestClient):
    r = _post(client, _GB, json={})
    assert r.status_code == 422


def test_gateway_bonds_create_with_mode(client: TestClient):
    r = _post(client, _GB, json={"name": "bond-lacp", "mode": "lacp"})
    assert r.status_code == 201
    assert "id" in r.json()


# ══════════════════════════════════════════════════════════════════════════════
# apply_schedules   /api/sdn/apply-schedules
# ══════════════════════════════════════════════════════════════════════════════

_AS = "/api/sdn/apply-schedules"


def test_apply_schedules_list_empty(client: TestClient):
    r = _get(client, _AS)
    assert r.status_code == 200
    assert r.json() == []


def test_apply_schedules_create(client: TestClient):
    r = _post(client, _AS, json={"name": "sched-test"})
    assert r.status_code == 201
    data = r.json()
    assert "id" in data
    assert data["name"] == "sched-test"


def test_apply_schedules_delete(client: TestClient):
    r = _post(client, _AS, json={"name": "sched-del"})
    assert r.status_code == 201
    rid = r.json()["id"]
    rd = _delete(client, f"{_AS}/{rid}")
    assert rd.status_code == 200
    assert rd.json()["status"] == "deleted"


def test_apply_schedules_delete_not_found(client: TestClient):
    rd = _delete(client, f"{_AS}/{uuid.uuid4()}")
    assert rd.status_code == 404


def test_apply_schedules_create_missing_required_field(client: TestClient):
    r = _post(client, _AS, json={})
    assert r.status_code == 422


# ══════════════════════════════════════════════════════════════════════════════
# mirror_sessions   /api/sdn/mirror-sessions
# ══════════════════════════════════════════════════════════════════════════════

_MS = "/api/sdn/mirror-sessions"


def test_mirror_sessions_list_empty(client: TestClient):
    r = _get(client, _MS)
    assert r.status_code == 200
    assert r.json() == []


def test_mirror_sessions_create(client: TestClient):
    r = _post(client, _MS, json={"name": "mirror-test"})
    assert r.status_code == 201
    data = r.json()
    assert "id" in data
    assert data["name"] == "mirror-test"


def test_mirror_sessions_delete(client: TestClient):
    r = _post(client, _MS, json={"name": "mirror-del"})
    assert r.status_code == 201
    rid = r.json()["id"]
    rd = _delete(client, f"{_MS}/{rid}")
    assert rd.status_code == 200
    assert rd.json()["status"] == "deleted"


def test_mirror_sessions_delete_not_found(client: TestClient):
    rd = _delete(client, f"{_MS}/{uuid.uuid4()}")
    assert rd.status_code == 404


def test_mirror_sessions_create_missing_required_field(client: TestClient):
    r = _post(client, _MS, json={})
    assert r.status_code == 422
