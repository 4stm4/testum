# SPDX-License-Identifier: MIT
"""Task completion notifier interface."""
from __future__ import annotations

from typing import Protocol


class Notifier(Protocol):
    async def notify_task_completion(
        self,
        *,
        task_run_id: str,
        automation_job_id: str | None,
        platform_name: str,
        platform_id: str,
        status: str,
        triggered_by: str = "manual",
        stdout_snippet: str = "",
    ) -> None:
        ...
