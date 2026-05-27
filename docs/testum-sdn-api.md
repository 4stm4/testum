# Testum SDN API — Contract Reference

> Internal API served by Testum itself.  
> Base: `/api/sdn` — mounted under the main Starlette app.  
> All endpoints require JWT session cookie (`Authorization` header or session cookie set by `POST /api/auth/login`).

---

## Authentication

All `/api/sdn/*` routes require a valid session. Unauthenticated requests return `401 {"error": "Authentication required"}`.

Roles accepted on every SDN endpoint: `admin`, `operator`, `viewer` (`ALL_ROLES`).  
Exceptions: project binding `POST`/`DELETE` requires `admin` or `operator`.

---

## Webhook Receiver

### `POST /webhooks/nervum`

Public path — no JWT required. Receives Nervum outbox events.

**HMAC validation** (optional): if `NERVUM_WEBHOOK_SECRET` is set, the request body is verified against `X-SDN-Signature: sha256=<hex>`. If the secret is empty, validation is skipped.

**Delivery deduplication**: `X-SDN-Delivery-Id` header. Duplicate delivery IDs are silently ignored (in-memory set, cleared when size > 1000).

Processing is **async** (`asyncio.create_task`) — the response returns immediately with `202 Accepted` before the event is written to DB.

Request body — Nervum event envelope (see `nervum-contract.md`):

```json
{
  "event_type":    "node.registered",
  "resource_type": "node",
  "resource_id":   "node-abc123",
  "schema_version": 2,
  "project_id":    null,
  "payload":       { ... }
}
```

**`resource_type` is required** — used to dispatch to the correct handler. Without it the event is silently ignored (watermark is still advanced).

Responses:

| Status | Meaning |
|---|---|
| `202 {"status": "accepted"}` | Event queued for async processing |
| `401 {"error": "Invalid signature"}` | HMAC mismatch (only when secret is set) |
| `400 {"error": "Invalid JSON"}` | Malformed body |
| `200 {"status": "duplicate"}` | Delivery ID already seen |

---

## Sync Status

### `GET /api/sdn/sync/status`

Returns replica state and per-resource row counts.

```json
{
  "watermark":            42,
  "subscription_id":      "sub_...",
  "last_synced_at":       "2026-05-27T10:00:00",
  "consecutive_failures": 0,
  "nervum_url":           "http://nervum:8080",
  "nervum_configured":    true,
  "network_count":        5,
  "node_count":           3,
  "logical_port_count":   12,
  "router_count":         1,
  "floating_ip_count":    0,
  "security_group_count": 2,
  "..."
}
```

### `POST /api/sdn/sync/trigger`

Triggers a background delta resync from Nervum (calls `recover_delta`).

Responses: `202 {"message": "Resync started"}` or `503 {"error": "NERVUM_URL not configured"}`.

---

## Networks

Replica of Nervum networks. Testum can create networks directly (written to local DB and optionally pushed to Nervum).

### `GET /api/sdn/networks`

Query params:

| Param | Type | Effect |
|---|---|---|
| `project_id` | string | Filter by project |

Response: `200` — array of network objects.

```json
[
  {
    "id":             "uuid",
    "name":           "prod-flat",
    "type":           "flat",
    "project_id":     "proj-abc",
    "vni":            null,
    "vlan_id":        null,
    "mtu":            null,
    "intent_version": 0,
    "spec_hash":      null,
    "node_ids":       [],
    "labels":         {},
    "updated_at":     "2026-05-27T10:00:00"
  }
]
```

### `POST /api/sdn/networks`

Required fields:

| Field | Type | Notes |
|---|---|---|
| `name` | string | Required, non-empty after strip |

Optional fields:

| Field | Type | Notes |
|---|---|---|
| `type` | string | `flat`, `vlan`, `vxlan` |
| `project_id` | string | |
| `vni` | int | Cast via `int()` |
| `mtu` | int | Cast via `int()` |

Responses:

| Status | Body |
|---|---|
| `201` | `{"id": "<uuid>", "name": "<name>"}` |
| `422` | `{"error": "name is required"}` |

### `DELETE /api/sdn/networks/{id}`

Responses:

| Status | Body |
|---|---|
| `200` | `{"status": "deleted"}` |
| `404` | `{"error": "Not found"}` |

---

## Nodes

Read-only replica of Nervum nodes. Nodes arrive exclusively via webhook events — there is no `POST /api/sdn/nodes`.

### `GET /api/sdn/nodes`

No query params. Returns all nodes ordered by `name`.

```json
[
  {
    "id":            "node-abc",
    "name":          "gw-01",
    "mgmt_ip":       "10.0.0.1",
    "status":        "ready",
    "agent_version": "1.2.3",
    "roles":         ["gateway"],
    "labels":        {},
    "updated_at":    "2026-05-27T10:00:00"
  }
]
```

### `DELETE /api/sdn/nodes/{id}`

Removes node from local replica. Does **not** delete the node in Nervum.

Responses:

| Status | Body |
|---|---|
| `200` | `{"status": "deleted"}` |
| `404` | `{"error": "Not found"}` |

**Node lifecycle via webhooks:**

| `event_type` | Effect |
|---|---|
| `node.registered` | Upsert row (create or update all fields) |
| `node.enrolled` | Same as `registered` |
| `node.updated` | Same as `registered` |
| `node.removed` | Delete row |

---

## Logical Ports

### `GET /api/sdn/logical-ports`

Query params: `project_id` (optional filter).

### `GET /api/sdn/logical-ports/{port_id}`

Returns single port. `404` if not found.

### `POST /api/sdn/logical-ports`

Required: `name`, `network_id`. Optional: `project_id`, `mac_address`, `fixed_ips`, `device_id`, `device_owner`, `labels`.

### `DELETE /api/sdn/logical-ports/{id}`

---

## Routers

### `GET /api/sdn/routers`

Query params: `project_id`.

### `POST /api/sdn/routers`

Required: `name`. Optional: `project_id`, `external_network_id`, `labels`.

### `DELETE /api/sdn/routers/{id}`

---

## Project Bindings

Maps Testum project IDs to Nervum project IDs. Used to scope resource filters.

### `GET /api/sdn/projects`

Returns all bindings ordered by `created_at DESC`.

```json
[
  {
    "id":                  "uuid",
    "testum_project_id":   "tp-abc",
    "nervum_project_id":   "np-xyz",
    "nervum_project_slug": "my-project",
    "status":              "active",
    "last_sync_at":        null,
    "created_at":          "2026-05-27T10:00:00"
  }
]
```

### `POST /api/sdn/projects`

Required fields: `testum_project_id`, `nervum_project_id`.  
Optional: `nervum_project_slug`.

**Idempotent**: if `testum_project_id` already bound, returns the existing binding (no duplicate created).

Roles: `admin`, `operator` only.

Responses: `200` (existing) or `201` (new).

### `GET /api/sdn/projects/{binding_id}`

### `DELETE /api/sdn/projects/{binding_id}`

Roles: `admin`, `operator` only.

---

## Operations (SDN Tasks)

Read-only view of async Nervum operations tracked in Testum.

### `GET /api/sdn/operations`

Query params: `network_id`, `status`, `limit` (default 50).

### `GET /api/sdn/operations/{task_id}`

---

## Other replica resources

All follow the same pattern: `GET` (with optional `project_id` filter), `POST` (create), `DELETE /{id}`.

| Resource | Base path |
|---|---|
| Security Groups | `/api/sdn/security-groups` |
| Floating IPs | `/api/sdn/floating-ips` |
| VPN Tunnels | `/api/sdn/vpn-tunnels` |
| Load Balancers | `/api/sdn/load-balancers` |
| BGP Peers | `/api/sdn/bgp-peers` |
| Address Pools | `/api/sdn/address-pools` |
| Service Objects | `/api/sdn/service-objects` |
| QoS Policies | `/api/sdn/qos-policies` |
| Security Policies | `/api/sdn/security-policies` |
| Trunk Ports | `/api/sdn/trunk-ports` |
| Gateway Bonds | `/api/sdn/gateway-bonds` |
| Apply Schedules | `/api/sdn/apply-schedules` |
| Mirror Sessions | `/api/sdn/mirror-sessions` |

---

## Common Response Codes

| Code | Meaning |
|---|---|
| `200` | OK |
| `201` | Created |
| `202` | Accepted (async operation started) |
| `400` | Bad request / invalid JSON |
| `401` | Not authenticated |
| `403` | Insufficient role |
| `404` | Resource not found |
| `422` | Validation error (missing required field) |
| `503` | Nervum not configured |

---

## E2E Test Coverage

Contract is verified by:

| Test file | Coverage |
|---|---|
| `tests/e2e/test_sdn_networks.py` | Networks CRUD, Create form, table, webhook→UI (36 tests) |
| `tests/e2e/test_sdn_nodes.py` | Nodes API, delete, webhook→UI (20 tests) |
| `tests/e2e/test_sdn_ui.py` | SDN page, tab nav, project bindings UI |
