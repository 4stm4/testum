"""HTTP client for Nervum SDN controller API.

Contract reference: docs/nervum-contract.md
Frozen against: Nervum v0.1.0 / OpenAPI artifact docs/nervum-openapi.json
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import time
import uuid
from typing import Any

import httpx

from app.config import config

logger = logging.getLogger(__name__)

_CONNECT_TIMEOUT = 5.0
_READ_TIMEOUT    = 30.0
_MAX_RETRIES     = 3
_RETRY_STATUSES  = {429, 500, 502, 503, 504}

SUPPORTED_SCHEMA_VERSION = 2


def _base_headers(task_id: str | None = None) -> dict[str, str]:
    h: dict[str, str] = {
        "Content-Type": "application/json",
        "X-Request-Id": str(uuid.uuid4()),
    }
    if config.NERVUM_TOKEN:
        h["Authorization"] = f"Bearer {config.NERVUM_TOKEN}"
    if task_id:
        h["X-Source-Task-Id"] = task_id
    return h


async def _request(
    method: str,
    url: str,
    *,
    task_id: str | None = None,
    json: Any = None,
    params: dict | None = None,
) -> httpx.Response:
    """Execute an HTTP request with exponential-backoff retries on transient errors."""
    timeout = httpx.Timeout(_READ_TIMEOUT, connect=_CONNECT_TIMEOUT)
    last_exc: Exception | None = None

    for attempt in range(_MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=timeout) as c:
                r = await c.request(
                    method,
                    url,
                    headers=_base_headers(task_id),
                    json=json,
                    params=params,
                )
            if r.status_code not in _RETRY_STATUSES:
                r.raise_for_status()
                return r
            last_exc = httpx.HTTPStatusError(
                f"HTTP {r.status_code}", request=r.request, response=r
            )
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            last_exc = exc

        wait = 2 ** attempt  # 1s, 2s, 4s
        logger.warning(
            "nervum: attempt %d/%d failed (%s) — retrying in %ds",
            attempt + 1, _MAX_RETRIES, last_exc, wait,
        )
        await asyncio.sleep(wait)

    raise RuntimeError(f"nervum: all {_MAX_RETRIES} attempts failed: {last_exc}") from last_exc


class NervumClient:
    """Typed async client for the Nervum SDN northbound API."""

    def __init__(self) -> None:
        self._base = (config.NERVUM_URL or "").rstrip("/")

    def _url(self, path: str) -> str:
        return f"{self._base}/api/v1{path}"

    # ── Events / Snapshot ────────────────────────────────────────────────

    async def get_snapshot(self) -> dict:
        """GET /events/snapshot → {event_id, networks:[], nodes:[]}."""
        r = await _request("GET", self._url("/events/snapshot"))
        return r.json()

    async def get_events(self, since: int, limit: int = 200) -> dict:
        """GET /events?since=<id> → {head_event_id, items:[OutboxEventOut]}.

        Caller accesses data["items"] and data["head_event_id"].
        """
        r = await _request(
            "GET", self._url("/events"),
            params={"since": since, "limit": min(limit, 1000)},
        )
        return r.json()

    # ── Webhook subscriptions ─────────────────────────────────────────────

    async def register_webhook(self, callback_url: str) -> dict:
        """POST /webhooks → {subscription:{id,...}, secret_plaintext}.

        The secret is returned ONCE — store in NERVUM_WEBHOOK_SECRET immediately.
        Field name is ``target_url`` (not ``url``).
        """
        r = await _request(
            "POST", self._url("/webhooks"),
            json={
                "target_url": callback_url,
                "event_types": ["*"],
                "description": "testum-sync",
                "labels": {"source": config.NERVUM_SA_NAME},
            },
        )
        return r.json()  # {subscription: {id, state, ...}, secret_plaintext: "..."}

    async def delete_webhook(self, subscription_id: str) -> None:
        """DELETE /webhooks/{id} — 204 or 404 are both acceptable."""
        try:
            await _request("DELETE", self._url(f"/webhooks/{subscription_id}"))
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 404:
                raise

    # ── Operations ────────────────────────────────────────────────────────

    async def create_logical_port(
        self,
        network_id: str,
        *,
        name: str,
        project_id: str | None = None,
        task_id: str | None = None,
    ) -> dict:
        """POST /networks/{network_id}/logical-ports → LogicalPortOut.

        Returns dict with at minimum: id, name, status, mac, ip_address.
        The operation may be asynchronous; caller should poll if needed.
        """
        payload: dict = {"name": name}
        if project_id:
            payload["project_id"] = project_id
        r = await _request(
            "POST",
            self._url(f"/networks/{network_id}/logical-ports"),
            task_id=task_id,
            json=payload,
        )
        return r.json()

    async def delete_logical_port(
        self,
        port_id: str,
        *,
        task_id: str | None = None,
    ) -> None:
        """DELETE /logical-ports/{port_id} — 204 or 404 are both acceptable."""
        try:
            await _request("DELETE", self._url(f"/logical-ports/{port_id}"), task_id=task_id)
        except Exception as exc:
            # 404 means already gone — treat as success
            if "404" in str(exc):
                return
            raise

    async def get_operation(self, operation_id: str) -> dict:
        """GET /operations/{id} → OperationOut."""
        r = await _request("GET", self._url(f"/operations/{operation_id}"))
        return r.json()

    async def poll_operation(
        self,
        operation_id: str,
        *,
        poll_interval: float = 2.0,
        timeout: float = 300.0,
    ) -> dict:
        """Poll until the operation reaches a terminal state and return OperationOut.

        Terminal states: succeeded | failed | cancelled | rolled_back
        Raises RuntimeError on timeout.
        """
        _TERMINAL = {"succeeded", "failed", "cancelled", "rolled_back"}
        deadline = time.monotonic() + timeout

        while True:
            op = await self.get_operation(operation_id)
            if op.get("status") in _TERMINAL:
                return op
            if time.monotonic() > deadline:
                raise RuntimeError(
                    f"nervum: operation {operation_id} timed out after {timeout}s"
                    f" (last status: {op.get('status')})"
                )
            await asyncio.sleep(poll_interval)


# ── HMAC validation ───────────────────────────────────────────────────────


def verify_signature(raw_body: bytes, header_value: str, secret: str) -> bool:
    """Validate X-SDN-Signature: sha256=<hex> against raw request body bytes.

    Nervum signs the raw body bytes directly — NOT re-serialized JSON.
    Source: nervum/src/sdn_controller/adapters/webhook.py::hmac_signature()

        hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
    """
    if not header_value or not header_value.startswith("sha256="):
        return False
    expected = header_value[7:]
    computed = hmac.new(
        secret.encode("utf-8"),
        raw_body,           # ← raw bytes, not re-serialized JSON
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(computed, expected)
