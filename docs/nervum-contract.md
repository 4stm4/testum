# Nervum SDN — Contract Reference for Testum

> Frozen against Nervum `v0.1.0` · OpenAPI artifact: `docs/nervum-openapi.json`
> Minimum Nervum features required: N0 (projects, service-accounts, webhooks, events)

---

## Base URL

```
http://<nervum-host>:8080/api/v1
```

Auth: `Authorization: Bearer <token>` on every request.

---

## Authentication

| Token type | How to obtain | Scope |
|---|---|---|
| Bootstrap admin token | `SDN_AUTH_BOOTSTRAP_ADMIN_TOKEN` env on first start | Global admin — only for initial SA creation |
| Service account token | `POST /api/v1/service-accounts` → `POST /api/v1/service-accounts/{id}/tokens` | Scoped to assigned project(s) |

Testum uses service account `testum-sync` with permissions: `webhook:read`, `webhook:write`, `network:read`, `node:read`.

---

## Request Tracing Headers

Every Testum→Nervum request MUST include:

| Header | Value |
|---|---|
| `Authorization` | `Bearer <token>` |
| `X-Request-Id` | `uuid4()` — correlation id |
| `X-Source-Task-Id` | Testum task id for mutating calls (optional on reads) |

---

## Event Envelope (schema_version=2)

`GET /api/v1/events` returns `EventsPageResponse`:

```json
{
  "head_event_id": 42,
  "items": [
    {
      "event_id": 42,
      "id": "outbox_a3f...",
      "event_type": "network.created",
      "resource_type": "network",
      "resource_id": "net_b5c...",
      "schema_version": 2,
      "project_id": "proj_xyz",
      "occurred_at": "2026-05-23T12:00:00Z",
      "payload": {}
    }
  ]
}
```

**Critical**: `items` is a list inside the wrapper. `head_event_id` is the current
watermark — use it to know if there are more pages.

`schema_version` MUST be checked. If `schema_version > 2`, route to quarantine.

---

## Snapshot

`GET /api/v1/events/snapshot` returns:

```json
{
  "event_id": 100,
  "networks": [ <NetworkOut> ],
  "nodes":    [ <NodeOut> ]
}
```

Use `event_id` as the initial watermark for `?since=`.

---

## Webhook Subscription

### Create

`POST /api/v1/webhooks`

```json
{
  "target_url": "https://testum.example.com/webhooks/nervum",
  "event_types": ["*"],
  "description": "testum-sync",
  "labels": {}
}
```

Response (secret returned **once only**):

```json
{
  "subscription": { "id": "sub_...", "state": "active", ... },
  "secret_plaintext": "abcdef..."
}
```

Store `subscription.id` and `secret_plaintext` (→ `NERVUM_WEBHOOK_SECRET` env).
Secret cannot be retrieved again.

### HMAC Validation

Nervum signs **raw request body bytes** (not re-serialized JSON):

```python
hmac.new(secret.encode("utf-8"), raw_body_bytes, hashlib.sha256).hexdigest()
# → "sha256=<hex>"  in header X-SDN-Signature
```

Delivery headers:
- `X-SDN-Event-Id`: event_id (integer as string)
- `X-SDN-Event-Type`: event_type string
- `X-SDN-Delivery-Id`: unique per delivery attempt
- `X-SDN-Signature`: `sha256=<hex>`

---

## Operation State Machine

Every mutating call returns an `operation_id`. States:

```
accepted → planning → running → verifying → succeeded ✓
                                          ↘ failed ✗
                                          ↘ rolled_back ✗
                             ↘ cancelled ✗
```

Poll: `GET /api/v1/operations/{operation_id}` until `status.is_terminal`.

```json
{
  "id": "op_...",
  "kind": "network.create",
  "status": "succeeded",
  "resource": {"type": "network", "id": "net_..."},
  "created_by": "sa:testum-sync",
  "events": [ {"sequence": 1, "status": "accepted", "message": "..."} ],
  "error": null
}
```

---

## Known Event Types

| event_type | resource_type | Trigger |
|---|---|---|
| `network.created` | network | POST /networks success |
| `network.updated` | network | PATCH /networks/{id} |
| `network.nodes_assigned` | network | node list changed |
| `network.applied` | network | apply operation succeeded |
| `network.apply_failed` | network | apply operation failed |
| `node.registered` | node | POST /nodes |
| `node.enrolled` | node | agent first contact |
| `node.removed` | node | DELETE /nodes/{id} |

---

## Network schema (`NetworkOut`)

Key fields relevant to Testum replica:

| Field | Type | Notes |
|---|---|---|
| `id` | string | nervum resource id |
| `name` | string | |
| `type` | enum | `flat`, `vlan`, `vxlan` |
| `mtu` | int | |
| `vlan_id` | int\|null | |
| `vni` | int\|null | |
| `project_id` | string\|null | **required for T2** |
| `intent_version` | int | mutation counter |
| `spec_hash` | string | desired-state hash |
| `node_ids` | list[str] | |
| `labels` | dict | |
| `created_at` | datetime | |
| `updated_at` | datetime | |

---

## Node schema (`NodeOut`)

| Field | Type | Notes |
|---|---|---|
| `id` | string | |
| `name` | string | |
| `mgmt_ip` | string | |
| `status` | enum | `pending`, `online`, `stale`, `offline`, `draining` |
| `roles` | list[str] | |
| `agent_version` | string\|null | |
| `labels` | dict | |
| `last_seen_at` | datetime\|null | |
| `created_at` | datetime | |
| `updated_at` | datetime | |

---

## Known Limitations (N0–N5 status)

| Block | Status |
|---|---|
| N0 — Projects, RBAC, Service Accounts, Webhooks, Events | ✅ Production-ready |
| N1 — LogicalPort, SecurityGroup, AddressPool, ServiceObject, QoSPolicy | ✅ Production-ready |
| N2 — SecurityPolicy (nftables compile/apply/drift), TrunkPort | ✅ Production-ready |
| N3 — Router, FloatingIP, BGP Peer, HA/VRRP | ✅ Production-ready |
| N4 — Quotas, Preflight, Snapshots, GatewayBond, LB | ✅ Production-ready |
| N5 — ApplySchedule, MirrorSession, VPN Tunnels | ✅ Production-ready |
| Operations state machine | ✅ Full `accepted→verifying→succeeded/failed/rolled_back` |
| Drift detection | ✅ Per-network drift scan |
| Backup/Restore | ✅ Full snapshot export/import |
| OpenTelemetry | ✅ Optional via `SDN_OTEL_ENABLED` |
