"""T3: Bootstrap a Nervum service account for Testum.

Run once via CLI:
    python -m adapters.nervum.bootstrap

Uses NERVUM_BOOTSTRAP_TOKEN (admin) to create the 'testum-sync' service
account and issue a long-lived token. Prints the token — operator must
set NERVUM_TOKEN env var with the output.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from app.config import config
from adapters.nervum.client import _request

logger = logging.getLogger(__name__)

_SA_NAME = "testum-sync"
_SA_ROLE = "admin"          # needs webhook:write + network:read + node:read
_TOKEN_TTL = 365 * 24 * 3600   # 1 year in seconds


async def _bootstrap() -> None:
    if not config.NERVUM_URL:
        print("ERROR: NERVUM_URL not set", file=sys.stderr)
        sys.exit(1)
    if not config.NERVUM_BOOTSTRAP_TOKEN:
        print("ERROR: NERVUM_BOOTSTRAP_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    import httpx, uuid
    base = config.NERVUM_URL.rstrip("/") + "/api/v1"
    headers = {
        "Authorization": f"Bearer {config.NERVUM_BOOTSTRAP_TOKEN}",
        "Content-Type":  "application/json",
        "X-Request-Id":  str(uuid.uuid4()),
    }

    async with httpx.AsyncClient(timeout=15) as c:
        # 1. Check if SA already exists
        r = await c.get(f"{base}/service-accounts", headers=headers)
        r.raise_for_status()
        existing = [sa for sa in r.json().get("items", []) if sa["name"] == _SA_NAME]

        if existing:
            sa_id = existing[0]["id"]
            print(f"Service account '{_SA_NAME}' already exists: {sa_id}")
        else:
            r = await c.post(
                f"{base}/service-accounts",
                json={"name": _SA_NAME, "role": _SA_ROLE,
                      "description": "Testum SDN sync service account",
                      "labels": {"managed-by": "testum"}},
                headers=headers,
            )
            r.raise_for_status()
            sa_id = r.json()["id"]
            print(f"Created service account '{_SA_NAME}': {sa_id}")

        # 2. Issue a token
        r = await c.post(
            f"{base}/service-accounts/{sa_id}/tokens",
            json={"ttl_seconds": _TOKEN_TTL, "label": "testum-primary"},
            headers=headers,
        )
        r.raise_for_status()
        data = r.json()
        token = data.get("token_plaintext", "")

    print()
    print("=" * 60)
    print("Set the following environment variable in Testum:")
    print(f"  NERVUM_TOKEN={token}")
    print("=" * 60)
    print("Token is shown ONCE — store it securely.")


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(_bootstrap())


if __name__ == "__main__":
    main()
