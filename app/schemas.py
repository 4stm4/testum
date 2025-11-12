"""Pydantic schemas for request and response validation."""
from datetime import datetime
from typing import Optional, List, Dict
from uuid import UUID
from pydantic import BaseModel, Field


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
