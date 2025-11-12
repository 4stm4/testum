"""SQLAlchemy database models."""
import uuid
from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    String,
    Integer,
    Text,
    LargeBinary,
    DateTime,
    Enum,
    ForeignKey,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import CHAR, TypeDecorator
from sqlalchemy.orm import relationship
import enum

from app.db import Base


class GUID(TypeDecorator):
    """Platform-independent GUID type."""

    impl = PG_UUID
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value if dialect.name == "postgresql" else str(value)
        return str(uuid.UUID(str(value)))

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


class UserRole(str, enum.Enum):
    """Role-based access control roles."""

    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


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

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    public_key = Column(Text, nullable=False)
    encrypted_private_key = Column(LargeBinary, nullable=True)  # Encrypted private key for authentication
    created_by = Column(String(255), nullable=True)  # For future user system
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<SSHKey(id={self.id}, name={self.name})>"


class User(Base):
    """Application user with RBAC role."""

    __tablename__ = "users"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    username = Column(String(150), nullable=False, unique=True, index=True)
    email = Column(String(255), nullable=True, unique=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(
        Enum(UserRole, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=UserRole.OPERATOR,
        index=True,
    )
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, role={self.role})>"


class Platform(Base):
    """Platform (host) model."""
    __tablename__ = "platforms"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True, index=True)
    host = Column(String(255), nullable=False)
    port = Column(Integer, default=22, nullable=False)
    username = Column(String(255), nullable=False)
    auth_method = Column(Enum(AuthMethodEnum, values_callable=lambda x: [e.value for e in x]), nullable=False)
    
    # Encrypted credentials
    encrypted_password = Column(LargeBinary, nullable=True)
    encrypted_private_key = Column(LargeBinary, nullable=True)  # Legacy, use ssh_key_id instead
    
    # SSH Key reference (for private_key auth method)
    ssh_key_id = Column(GUID(), ForeignKey("ssh_keys.id"), nullable=True)
    
    # Host key fingerprint for verification
    known_host_fingerprint = Column(String(255), nullable=True)

    # Cached system information collected during connection test
    system_info = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    ssh_key = relationship("SSHKey")
    task_runs = relationship("TaskRun", back_populates="platform")

    def __repr__(self):
        return f"<Platform(id={self.id}, name={self.name}, host={self.host})>"


class TaskRun(Base):
    """Task execution record."""
    __tablename__ = "task_runs"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    celery_task_id = Column(String(255), nullable=True, unique=True, index=True)
    type = Column(Enum(TaskTypeEnum, values_callable=lambda x: [e.value for e in x]), nullable=False, index=True)

    # Platform reference
    platform_id = Column(GUID(), ForeignKey("platforms.id"), nullable=True)
    platform = relationship("Platform", back_populates="task_runs")
    
    # Status
    status = Column(Enum(TaskStatusEnum, values_callable=lambda x: [e.value for e in x]), default=TaskStatusEnum.PENDING, nullable=False, index=True)
    
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


class Script(Base):
    """Reusable automation script."""

    __tablename__ = "scripts"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True, index=True)
    language = Column(String(50), nullable=False, default="bash")
    description = Column(Text, nullable=True)
    content = Column(Text, nullable=False)
    created_by = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Script(id={self.id}, name={self.name}, language={self.language})>"


class AutomationExecutionEnum(str, enum.Enum):
    """Execution strategy for automation jobs."""

    COMMAND = "command"
    SCRIPT = "script"


class AutomationTriggerEnum(str, enum.Enum):
    """Trigger type for automation jobs."""

    MANUAL = "manual"
    CRON = "cron"
    GITHUB_PUSH = "github_push"
    WEBHOOK = "webhook"


class AutomationJob(Base):
    """Reusable automation definition with scheduling and triggers."""

    __tablename__ = "automation_jobs"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    execution_type = Column(
        Enum(AutomationExecutionEnum, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=AutomationExecutionEnum.COMMAND,
    )
    command = Column(Text, nullable=True)
    script_id = Column(GUID(), ForeignKey("scripts.id"), nullable=True)
    trigger_type = Column(
        Enum(AutomationTriggerEnum, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=AutomationTriggerEnum.MANUAL,
    )
    cron_expression = Column(String(255), nullable=True)
    repository_url = Column(String(512), nullable=True)
    repository_branch = Column(String(120), nullable=True)
    webhook_secret = Column(String(255), nullable=True)
    environment = Column(JSON, nullable=True)
    parameters = Column(JSON, nullable=True)
    tags = Column(JSON, nullable=True)
    notification_settings = Column(JSON, nullable=True)
    timeout_seconds = Column(Integer, default=600, nullable=False)
    max_retries = Column(Integer, default=0, nullable=False)
    retry_delay_seconds = Column(Integer, default=60, nullable=False)
    concurrency_limit = Column(Integer, nullable=True)
    require_approval = Column(Boolean, default=False, nullable=False)
    run_on_all_platforms = Column(Boolean, default=False, nullable=False)
    notes = Column(Text, nullable=True)
    is_enabled = Column(Boolean, default=True, nullable=False)
    created_by = Column(String(255), nullable=True)
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    script = relationship("Script")
    platform_links = relationship(
        "AutomationJobPlatform",
        back_populates="job",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<AutomationJob(id={self.id}, name={self.name}, trigger={self.trigger_type})>"


class AutomationJobPlatform(Base):
    """Association table between automation jobs and platforms."""

    __tablename__ = "automation_job_platforms"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    job_id = Column(GUID(), ForeignKey("automation_jobs.id", ondelete="CASCADE"), nullable=False)
    platform_id = Column(GUID(), ForeignKey("platforms.id", ondelete="CASCADE"), nullable=False)

    job = relationship("AutomationJob", back_populates="platform_links")
    platform = relationship("Platform")

    __table_args__ = (
        UniqueConstraint("job_id", "platform_id", name="uq_automation_job_platform"),
    )


class AuditLog(Base):
    """Audit log for tracking actions."""
    __tablename__ = "audit_logs"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user = Column(String(255), nullable=False, index=True)
    action = Column(String(255), nullable=False, index=True)
    object_type = Column(String(100), nullable=False, index=True)
    object_id = Column(String(255), nullable=True, index=True)
    meta = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f"<AuditLog(id={self.id}, user={self.user}, action={self.action})>"
