"""SQLAlchemy database models."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, LargeBinary, DateTime, Enum, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from app.db import Base


class AuthMethodEnum(str, enum.Enum):
    """Authentication method enum."""
    PASSWORD = "password"
    PRIVATE_KEY = "private_key"


class TaskTypeEnum(str, enum.Enum):
    """Task type enum."""
    DEPLOY = "deploy"
    RUN_COMMAND = "run_command"


class TaskStatusEnum(str, enum.Enum):
    """Task status enum."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class SSHKey(Base):
    """SSH key pair model."""
    __tablename__ = "ssh_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    public_key = Column(Text, nullable=False)
    encrypted_private_key = Column(LargeBinary, nullable=True)  # Encrypted private key for authentication
    created_by = Column(String(255), nullable=True)  # For future user system
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<SSHKey(id={self.id}, name={self.name})>"


class Platform(Base):
    """Platform (host) model."""
    __tablename__ = "platforms"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True, index=True)
    host = Column(String(255), nullable=False)
    port = Column(Integer, default=22, nullable=False)
    username = Column(String(255), nullable=False)
    auth_method = Column(Enum(AuthMethodEnum, values_callable=lambda x: [e.value for e in x]), nullable=False)
    
    # Encrypted credentials
    encrypted_password = Column(LargeBinary, nullable=True)
    encrypted_private_key = Column(LargeBinary, nullable=True)  # Legacy, use ssh_key_id instead
    
    # SSH Key reference (for private_key auth method)
    ssh_key_id = Column(UUID(as_uuid=True), ForeignKey("ssh_keys.id"), nullable=True)
    
    # Host key fingerprint for verification
    known_host_fingerprint = Column(String(255), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    ssh_key = relationship("SSHKey")
    task_runs = relationship("TaskRun", back_populates="platform")

    def __repr__(self):
        return f"<Platform(id={self.id}, name={self.name}, host={self.host})>"


class TaskRun(Base):
    """Task execution record."""
    __tablename__ = "task_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    celery_task_id = Column(String(255), nullable=False, unique=True, index=True)
    type = Column(Enum(TaskTypeEnum), nullable=False, index=True)
    
    # Platform reference
    platform_id = Column(UUID(as_uuid=True), ForeignKey("platforms.id"), nullable=True)
    platform = relationship("Platform", back_populates="task_runs")
    
    # Status
    status = Column(Enum(TaskStatusEnum), default=TaskStatusEnum.PENDING, nullable=False, index=True)
    
    # Results
    result_location = Column(String(512), nullable=True)  # S3 key or path
    stdout = Column(Text, nullable=True)  # For small outputs
    stderr = Column(Text, nullable=True)  # For small outputs
    error_message = Column(Text, nullable=True)
    
    # Additional data
    task_metadata = Column(JSON, nullable=True)  # Additional task-specific data
    
    # Timestamps
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<TaskRun(id={self.id}, type={self.type}, status={self.status})>"


class AuditLog(Base):
    """Audit log for tracking actions."""
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user = Column(String(255), nullable=False, index=True)
    action = Column(String(255), nullable=False, index=True)
    object_type = Column(String(100), nullable=False, index=True)
    object_id = Column(String(255), nullable=True, index=True)
    meta = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f"<AuditLog(id={self.id}, user={self.user}, action={self.action})>"
