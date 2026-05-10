# SPDX-License-Identifier: MIT
"""Job queue interface."""
from __future__ import annotations

from typing import Any, Dict, Protocol


class JobQueue(Protocol):
    async def enqueue(
        self,
        kind: str,
        payload: Dict[str, Any],
        *,
        max_attempts: int = 1,
    ) -> str:
        """Enqueue a job; return job id."""
        ...

    async def cancel(self, job_id: str) -> bool:
        """Cancel a pending or running job."""
        ...
