"""HTTP client for nervum SDN controller API."""
import hashlib
import hmac
import json
import logging
import uuid
from typing import Any

import httpx

from app.config import config

logger = logging.getLogger(__name__)

_HEADERS_BASE = {"Content-Type": "application/json"}


def _headers(task_id: str | None = None) -> dict:
    h = {**_HEADERS_BASE, "X-Request-Id": str(uuid.uuid4())}
    if config.NERVUM_TOKEN:
        h["Authorization"] = f"Bearer {config.NERVUM_TOKEN}"
    if task_id:
        h["X-Source-Task-Id"] = task_id
    return h


class NervumClient:
    def __init__(self):
        self.base = (config.NERVUM_URL or "").rstrip("/")

    async def get_snapshot(self) -> dict:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(f"{self.base}/api/v1/events/snapshot", headers=_headers())
            r.raise_for_status()
            return r.json()

    async def get_events(self, since: int, limit: int = 200) -> list[dict]:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(
                f"{self.base}/api/v1/events",
                params={"since": since, "limit": limit},
                headers=_headers(),
            )
            r.raise_for_status()
            return r.json()

    async def register_webhook(self, callback_url: str) -> dict:
        """Register a webhook subscription. Returns {subscription_id, secret}."""
        body = {
            "url": callback_url,
            "event_types": ["*"],
            "source_name": config.NERVUM_SA_NAME,
        }
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(
                f"{self.base}/api/v1/webhooks",
                json=body,
                headers=_headers(),
            )
            r.raise_for_status()
            return r.json()

    async def delete_webhook(self, subscription_id: str) -> None:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.delete(
                f"{self.base}/api/v1/webhooks/{subscription_id}",
                headers=_headers(),
            )
            if r.status_code not in (200, 204, 404):
                r.raise_for_status()


def verify_signature(raw_body: bytes, header_value: str, secret: str) -> bool:
    """Validate X-SDN-Signature: sha256=<hex> against raw request body."""
    if not header_value or not header_value.startswith("sha256="):
        return False
    expected = header_value[7:]
    canonical = json.dumps(
        json.loads(raw_body.decode("utf-8")),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    computed = hmac.new(secret.encode("utf-8"), canonical, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, expected)
