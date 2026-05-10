# SPDX-License-Identifier: MIT
"""asyncssh implementation of the SSHClient interface."""
from __future__ import annotations

import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import asyncssh  # type: ignore
except ImportError:
    asyncssh = None  # type: ignore


class AsyncSSHClient:
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: Optional[str] = None,
        private_key: Optional[str] = None,
        known_host_fingerprint: Optional[str] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.private_key = private_key
        self.known_host_fingerprint = known_host_fingerprint
        self._conn = None

    async def connect(self) -> Tuple[bool, Optional[str]]:
        if asyncssh is None:
            return False, "asyncssh is not installed"
        try:
            kwargs: dict = dict(
                host=self.host,
                port=self.port,
                username=self.username,
                known_hosts=None,
                login_timeout=10,
            )
            if self.password:
                kwargs["password"] = self.password
            elif self.private_key:
                key = asyncssh.import_private_key(self.private_key)
                kwargs["client_keys"] = [key]
                kwargs["preferred_auth"] = ["publickey"]

            self._conn = await asyncssh.connect(**kwargs)
            return True, None
        except Exception as exc:
            logger.warning("SSH connect failed: %s", exc)
            return False, str(exc)

    async def execute_command(self, command: str, timeout: int = 60) -> Tuple[int, str, str]:
        if self._conn is None:
            raise RuntimeError("Not connected")
        result = await self._conn.run(command, timeout=timeout)
        return result.exit_status or 0, result.stdout or "", result.stderr or ""

    async def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
