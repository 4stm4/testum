# SPDX-License-Identifier: MIT
"""Pydantic schemas for request and response validation."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models import UserRole


# User Schemas
class UserCreate(BaseModel):
    """Schema for creating a user."""

    username: str = Field(..., min_length=3, max_length=150)
    password: str = Field(..., min_length=8, max_length=255)
    role: str = Field(default=UserRole.OPERATOR.value, pattern="^(admin|operator|viewer)$")
    email: Optional[str] = None

    @model_validator(mode="after")
    def _validate_email(cls, values: "UserCreate"):
        if values.email and "@" not in values.email:
            raise ValueError("Invalid email address")
        return values


class UserUpdate(BaseModel):
    """Schema for updating a user."""

    username: Optional[str] = Field(default=None, min_length=3, max_length=150)
    password: Optional[str] = Field(default=None, min_length=8, max_length=255)
    role: Optional[str] = Field(default=None, pattern="^(admin|operator|viewer)$")
    email: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    """Schema representing user details."""

    id: UUID
    username: str
    email: Optional[str]
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


# SSH Key Schemas
class SSHKeyCreate(BaseModel):
    """Schema for creating SSH key."""
    name: str = Field(..., min_length=1, max_length=255)
    public_key: str = Field(..., min_length=1)
    private_key: Optional[str] = None  # Optional: encrypted and stored for authentication


class SSHKeyResponse(BaseModel):
    """Schema for SSH key response."""
    id: UUID
    name: str
    public_key: str
    has_private_key: bool = False  # Indicator if private key is stored
    created_by: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# Platform Schemas
class PlatformCreate(BaseModel):
    """Schema for creating platform."""
    name: str = Field(..., min_length=1, max_length=255)
    host: str = Field(..., min_length=1, max_length=255)
    port: int = Field(default=22, ge=1, le=65535)
    username: str = Field(..., min_length=1, max_length=255)
    auth_method: str = Field(..., pattern="^(password|private_key)$")
    password: Optional[str] = None
    ssh_key_id: Optional[UUID] = None  # Reference to SSHKey for private_key auth


class PlatformUpdate(BaseModel):
    """Schema for updating platform."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    host: Optional[str] = Field(None, min_length=1, max_length=255)
    port: Optional[int] = Field(None, ge=1, le=65535)
    username: Optional[str] = Field(None, min_length=1, max_length=255)
    auth_method: Optional[str] = Field(None, pattern="^(password|private_key)$")
    password: Optional[str] = None
    ssh_key_id: Optional[UUID] = None


class PlatformResponse(BaseModel):
    """Schema for platform response (without sensitive data)."""
    id: UUID
    name: str
    host: str
    port: int
    username: str
    auth_method: str
    has_password: bool = Field(default=False)
    has_private_key: bool = Field(default=False)
    known_host_fingerprint: Optional[str]
    system_info: Optional[Dict[str, str]] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Script Schemas
class ScriptBase(BaseModel):
    """Shared fields for script payloads."""

    name: str = Field(..., min_length=1, max_length=255)
    language: str = Field(default="bash", min_length=1, max_length=50)
    description: Optional[str] = Field(default=None, max_length=2000)
    content: str = Field(..., min_length=1)


class ScriptCreate(ScriptBase):
    """Schema for creating a script."""


class ScriptUpdate(BaseModel):
    """Schema for updating a script."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    language: Optional[str] = Field(default=None, min_length=1, max_length=50)
    description: Optional[str] = Field(default=None, max_length=2000)
    content: Optional[str] = Field(default=None, min_length=1)


class ScriptResponse(BaseModel):
    """Schema for script responses."""

    id: UUID
    name: str
    language: str
    description: Optional[str]
    content: str
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Automation Schemas
class AutomationJobBase(BaseModel):
    """Shared schema for automation jobs."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=4000)
    execution_type: str = Field(..., pattern="^(command|script)$")
    command: Optional[str] = Field(default=None, min_length=1)
    script_id: Optional[UUID] = None
    trigger_type: str = Field(..., pattern="^(manual|cron|github_push|webhook)$")
    cron_expression: Optional[str] = Field(default=None, max_length=255)
    repository_url: Optional[str] = Field(default=None, max_length=512)
    repository_branch: Optional[str] = Field(default=None, max_length=120)
    webhook_secret: Optional[str] = Field(default=None, max_length=255)
    environment: Dict[str, Any] = Field(default_factory=dict)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    notification_settings: Dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=600, ge=1, le=86400)
    max_retries: int = Field(default=0, ge=0, le=10)
    retry_delay_seconds: int = Field(default=60, ge=0, le=3600)
    concurrency_limit: Optional[int] = Field(default=None, ge=1, le=100)
    require_approval: bool = Field(default=False)
    run_on_all_platforms: bool = Field(default=False)
    notes: Optional[str] = Field(default=None, max_length=4000)
    is_enabled: bool = Field(default=True)

    @model_validator(mode="after")
    def _validate_base(self):
        """Validate base configuration combinations."""
        if self.execution_type == "command" and not self.command:
            raise ValueError("command is required when execution_type is 'command'")
        if self.execution_type == "script" and not self.script_id:
            raise ValueError("script_id is required when execution_type is 'script'")
        if self.trigger_type == "cron" and not self.cron_expression:
            raise ValueError("cron_expression is required for cron trigger")
        if self.trigger_type == "github_push" and not self.repository_url:
            raise ValueError("repository_url is required for GitHub triggers")
        if self.trigger_type == "webhook" and not self.webhook_secret:
            raise ValueError("webhook_secret is required for webhook triggers")
        return self


class AutomationJobCreate(AutomationJobBase):
    """Schema for creating an automation job."""

    target_platform_ids: List[UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_targets(self):
        if not self.run_on_all_platforms and not self.target_platform_ids:
            raise ValueError("target_platform_ids are required when run_on_all_platforms is False")
        return self


class AutomationJobUpdate(BaseModel):
    """Schema for updating an automation job."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=4000)
    execution_type: Optional[str] = Field(default=None, pattern="^(command|script)$")
    command: Optional[str] = Field(default=None, min_length=1)
    script_id: Optional[UUID] = None
    trigger_type: Optional[str] = Field(default=None, pattern="^(manual|cron|github_push|webhook)$")
    cron_expression: Optional[str] = Field(default=None, max_length=255)
    repository_url: Optional[str] = Field(default=None, max_length=512)
    repository_branch: Optional[str] = Field(default=None, max_length=120)
    webhook_secret: Optional[str] = Field(default=None, max_length=255)
    environment: Optional[Dict[str, Any]] = None
    parameters: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    notification_settings: Optional[Dict[str, Any]] = None
    timeout_seconds: Optional[int] = Field(default=None, ge=1, le=86400)
    max_retries: Optional[int] = Field(default=None, ge=0, le=10)
    retry_delay_seconds: Optional[int] = Field(default=None, ge=0, le=3600)
    concurrency_limit: Optional[int] = Field(default=None, ge=1, le=100)
    require_approval: Optional[bool] = None
    run_on_all_platforms: Optional[bool] = None
    notes: Optional[str] = Field(default=None, max_length=4000)
    is_enabled: Optional[bool] = None
    target_platform_ids: Optional[List[UUID]] = None

    @model_validator(mode="after")
    def _validate_update(self):
        if self.execution_type == "command":
            if "command" in self.model_fields_set and not self.command:
                raise ValueError("command must be provided when execution_type is 'command'")
        if self.execution_type == "script":
            if "script_id" in self.model_fields_set and self.script_id is None:
                raise ValueError("script_id must be provided when execution_type is 'script'")
        if self.trigger_type == "cron":
            if "cron_expression" in self.model_fields_set and not self.cron_expression:
                raise ValueError("cron_expression must be provided for cron trigger")
        if self.trigger_type == "github_push":
            if "repository_url" in self.model_fields_set and not self.repository_url:
                raise ValueError("repository_url must be provided for GitHub trigger")
        if self.trigger_type == "webhook":
            if "webhook_secret" in self.model_fields_set and not self.webhook_secret:
                raise ValueError("webhook_secret must be provided for webhook trigger")
        return self


class AutomationJobTargetResponse(BaseModel):
    """Schema describing a selected platform for an automation job."""

    platform_id: UUID
    platform_name: Optional[str]

    class Config:
        from_attributes = True


class AutomationJobResponse(AutomationJobBase):
    """Schema returned for automation jobs."""

    id: UUID
    target_platform_ids: List[UUID]
    targets: List[AutomationJobTargetResponse]
    created_by: Optional[str]
    last_run_at: Optional[datetime]
    next_run_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Task Schemas
class DeployKeysRequest(BaseModel):
    """Schema for deploy keys request."""
    key_ids: Optional[List[UUID]] = Field(default=None, description="List of key IDs to deploy. If empty, deploy all.")


class RunCommandRequest(BaseModel):
    """Schema for run command request."""
    command: str = Field(..., min_length=1)
    timeout: int = Field(default=60, ge=1, le=3600)


class TaskResponse(BaseModel):
    """Schema for task response."""
    task_id: str
    status: str
    message: Optional[str] = None


class TaskStatusResponse(BaseModel):
    """Schema for task status response."""
    id: UUID
    celery_task_id: str
    type: str
    platform_id: Optional[UUID]
    status: str
    result_location: Optional[str]
    stdout: Optional[str]
    stderr: Optional[str]
    error_message: Optional[str]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# WebSocket Message Schemas
class WSMessage(BaseModel):
    """WebSocket message schema."""
    ts: datetime
    type: str = Field(..., pattern="^(stdout|stderr|progress|done|error)$")
    payload: str


# Auth Schemas
class LoginRequest(BaseModel):
    """Schema for login request."""
    username: str
    password: str


class TokenResponse(BaseModel):
    """Schema for token response."""
    access_token: str
    token_type: str = "bearer"


# Generic Response
class MessageResponse(BaseModel):
    """Generic message response."""
    message: str
