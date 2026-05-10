# SPDX-License-Identifier: MIT
"""SSH client interface."""
from __future__ import annotations

from typing import Optional, Protocol, Tuple


class SSHClient(Protocol):
    async def connect(self) -> Tuple[bool, Optional[str]]:
        """Return (success, error_message)."""
        ...

    async def execute_command(
        self, command: str, timeout: int = 60
    ) -> Tuple[int, str, str]:
        """Return (exit_code, stdout, stderr)."""
        ...

    async def close(self) -> None:
        ...
