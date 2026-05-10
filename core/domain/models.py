# SPDX-License-Identifier: MIT
"""Pure Python domain models — no SQLAlchemy, no external dependencies."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.domain.enums import (
    AuthMethod,
    ExecutionType,
    TaskStatus,
    TaskType,
    TriggerType,
    UserRole,
)


@dataclass
class User:
    id: str
    username: str
    hashed_password: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
    email: Optional[str] = None
    last_login: Optional[datetime] = None


@dataclass
class SSHKey:
    id: str
    name: str
    public_key: str
    created_at: datetime
    created_by: Optional[str] = None
    has_private_key: bool = False


@dataclass
class Platform:
    id: str
    name: str
    host: str
    port: int
    username: str
    auth_method: AuthMethod
    created_at: datetime
    ssh_key_id: Optional[str] = None
    known_host_fingerprint: Optional[str] = None
    system_info: Optional[Dict[str, Any]] = None


@dataclass
class TaskRun:
    id: str
    type: TaskType
    status: TaskStatus
    created_at: datetime
    platform_id: Optional[str] = None
    result_location: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    error_message: Optional[str] = None
    pyjobkit_job_id: Optional[str] = None
    task_metadata: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


@dataclass
class Script:
    id: str
    name: str
    language: str
    content: str
    created_at: datetime
    updated_at: datetime
    description: Optional[str] = None
    created_by: Optional[str] = None


@dataclass
class AutomationJob:
    id: str
    name: str
    execution_type: ExecutionType
    trigger_type: TriggerType
    timeout_seconds: int
    max_retries: int
    retry_delay_seconds: int
    is_enabled: bool
    run_on_all_platforms: bool
    require_approval: bool
    created_at: datetime
    updated_at: datetime
    description: Optional[str] = None
    command: Optional[str] = None
    script_id: Optional[str] = None
    cron_expression: Optional[str] = None
    repository_url: Optional[str] = None
    repository_branch: Optional[str] = None
    webhook_secret: Optional[str] = None
    environment: Optional[Dict[str, Any]] = None
    parameters: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    notification_settings: Optional[Dict[str, Any]] = None
    concurrency_limit: Optional[int] = None
    notes: Optional[str] = None
    created_by: Optional[str] = None
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    platform_ids: List[str] = field(default_factory=list)


@dataclass
class AuditLog:
    id: str
    user: str
    action: str
    object_type: str
    timestamp: datetime
    object_id: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
