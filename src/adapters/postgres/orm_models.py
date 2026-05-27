# SPDX-License-Identifier: MIT
"""SQLAlchemy ORM models."""
import enum
import json
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey,
    Integer, JSON, LargeBinary, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship
from sqlalchemy.types import CHAR, TypeDecorator

from adapters.postgres.session import Base


class GUID(TypeDecorator):
    """Platform-independent UUID type (PostgreSQL native / SQLite CHAR-36)."""

    impl = PG_UUID
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if not value or (isinstance(value, dict) and not value):
            return None
        try:
            uuid_obj = value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
            return uuid_obj if dialect.name == "postgresql" else str(uuid_obj)
        except (ValueError, AttributeError, TypeError):
            return None

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


class JSONString(TypeDecorator):
    impl = JSON
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        try:
            return json.loads(json.dumps(value, default=str))
        except Exception:
            return json.loads(json.dumps(str(value)))


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class AuthMethodEnum(str, enum.Enum):
    PASSWORD = "password"
    PRIVATE_KEY = "private_key"


class TaskTypeEnum(str, enum.Enum):
    DEPLOY = "deploy"
    RUN_COMMAND = "run_command"


class TaskStatusEnum(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class AutomationExecutionEnum(str, enum.Enum):
    COMMAND = "command"
    SCRIPT = "script"


class AutomationTriggerEnum(str, enum.Enum):
    MANUAL = "manual"
    CRON = "cron"
    GITHUB_PUSH = "github_push"
    WEBHOOK = "webhook"


class SSHKeyRow(Base):
    __tablename__ = "ssh_keys"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    public_key = Column(Text, nullable=False)
    encrypted_private_key = Column(LargeBinary, nullable=True)
    created_by = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class UserRow(Base):
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


class PlatformRow(Base):
    __tablename__ = "platforms"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True, index=True)
    host = Column(String(255), nullable=False)
    port = Column(Integer, default=22, nullable=False)
    username = Column(String(255), nullable=False)
    auth_method = Column(
        Enum(AuthMethodEnum, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    encrypted_password = Column(LargeBinary, nullable=True)
    encrypted_private_key = Column(LargeBinary, nullable=True)
    ssh_key_id = Column(GUID(), ForeignKey("ssh_keys.id"), nullable=True)
    known_host_fingerprint = Column(String(255), nullable=True)
    system_info = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    ssh_key = relationship("SSHKeyRow")
    task_runs = relationship("TaskRunRow", back_populates="platform")


class TaskRunRow(Base):
    __tablename__ = "task_runs"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    type = Column(
        Enum(TaskTypeEnum, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )
    platform_id = Column(GUID(), ForeignKey("platforms.id"), nullable=True)
    platform = relationship("PlatformRow", back_populates="task_runs")
    status = Column(
        Enum(TaskStatusEnum, values_callable=lambda x: [e.value for e in x]),
        default=TaskStatusEnum.PENDING,
        nullable=False,
        index=True,
    )
    result_location = Column(String(512), nullable=True)
    stdout = Column(Text, nullable=True)
    stderr = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    pyjobkit_job_id = Column(String(255), nullable=True, index=True)
    task_metadata = Column(JSON, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ScriptRow(Base):
    __tablename__ = "scripts"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True, index=True)
    language = Column(String(50), nullable=False, default="bash")
    description = Column(Text, nullable=True)
    content = Column(Text, nullable=False)
    created_by = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class AutomationJobRow(Base):
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

    script = relationship("ScriptRow")
    platform_links = relationship(
        "AutomationJobPlatformRow",
        back_populates="job",
        cascade="all, delete-orphan",
    )


class AutomationJobPlatformRow(Base):
    __tablename__ = "automation_job_platforms"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    job_id = Column(GUID(), ForeignKey("automation_jobs.id", ondelete="CASCADE"), nullable=False)
    platform_id = Column(GUID(), ForeignKey("platforms.id", ondelete="CASCADE"), nullable=False)

    job = relationship("AutomationJobRow", back_populates="platform_links")
    platform = relationship("PlatformRow")

    __table_args__ = (
        UniqueConstraint("job_id", "platform_id", name="uq_automation_job_platform"),
    )


class AuditLogRow(Base):
    __tablename__ = "audit_logs"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user = Column(String(255), nullable=False, index=True)
    action = Column(String(255), nullable=False, index=True)
    object_type = Column(String(100), nullable=False, index=True)
    object_id = Column(String(255), nullable=True, index=True)
    meta = Column(JSONString, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class NervumNetworkRow(Base):
    __tablename__ = "nervum_networks"

    id             = Column(String(255), primary_key=True)
    name           = Column(String(255), nullable=False, index=True)
    type           = Column(String(50),  nullable=True)
    project_id     = Column(String(255), nullable=True, index=True)   # T2 isolation key
    vni            = Column(Integer,     nullable=True)
    vlan_id        = Column(Integer,     nullable=True)
    mtu            = Column(Integer,     nullable=True)
    intent_version = Column(Integer,     nullable=True)
    spec_hash      = Column(String(255), nullable=True)
    node_ids       = Column(JSON,        nullable=True)               # list[str]
    labels         = Column(JSON,        nullable=True)               # dict[str,str]
    raw            = Column(JSON,        nullable=True)               # full NetworkOut
    updated_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class NervumNodeRow(Base):
    __tablename__ = "nervum_nodes"

    id            = Column(String(255), primary_key=True)
    name          = Column(String(255), nullable=False, index=True)
    mgmt_ip       = Column(String(100), nullable=True)
    status        = Column(String(50),  nullable=True, index=True)
    agent_version = Column(String(100), nullable=True)
    roles         = Column(JSON,        nullable=True)               # list[str]
    labels        = Column(JSON,        nullable=True)               # dict[str,str]
    raw           = Column(JSON,        nullable=True)               # full NodeOut
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class NervumSyncStateRow(Base):
    __tablename__ = "nervum_sync_state"

    id                   = Column(Integer,     primary_key=True, default=1)
    watermark            = Column(Integer,     nullable=False, default=0)
    subscription_id      = Column(String(255), nullable=True)
    last_synced_at       = Column(DateTime,    nullable=True)
    consecutive_failures = Column(Integer,     nullable=False, default=0)


class SdnTaskRow(Base):
    """T5: Bridge between a Testum task and a Nervum operation.

    Tracks the full lifecycle: accepted → planning → running → verifying →
    succeeded | failed | cancelled | rolled_back
    """

    __tablename__ = "sdn_tasks"

    id                  = Column(GUID(),      primary_key=True, default=uuid.uuid4)
    testum_task_id      = Column(String(255), nullable=True,  index=True)  # TaskRun.id if spawned
    nervum_operation_id = Column(String(255), nullable=False, index=True)
    project_id          = Column(String(255), nullable=True,  index=True)  # nervum project_id
    resource_type       = Column(String(100), nullable=True)
    resource_id         = Column(String(255), nullable=True)
    kind                = Column(String(100), nullable=True)               # network.create etc.
    status              = Column(String(50),  nullable=False, default="accepted", index=True)
    error_code          = Column(String(100), nullable=True)
    error_message       = Column(Text,        nullable=True)
    initiated_by        = Column(String(255), nullable=True)               # testum username
    started_at          = Column(DateTime,    default=datetime.utcnow, nullable=False)
    finished_at         = Column(DateTime,    nullable=True)
    updated_at          = Column(DateTime,    default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class NervumProjectBindingRow(Base):
    """Maps a Testum project to a Nervum project (T2).

    All SDN calls for a given Testum project MUST use nervum_project_id
    from this table. Resources created without a binding are rejected.
    """

    __tablename__ = "nervum_project_bindings"

    id                   = Column(GUID(),      primary_key=True, default=uuid.uuid4)
    testum_project_id    = Column(String(255), nullable=False, unique=True, index=True)
    nervum_project_id    = Column(String(255), nullable=False, index=True)
    nervum_project_slug  = Column(String(255), nullable=True)
    status               = Column(String(50),  nullable=False, default="active")  # active | suspended
    last_sync_at         = Column(DateTime,    nullable=True)
    created_at           = Column(DateTime,    default=datetime.utcnow, nullable=False)
    updated_at           = Column(DateTime,    default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


# ── T4: Full replica tables ───────────────────────────────────────────────


class NervumProjectRow(Base):
    """Replica of Nervum project objects."""

    __tablename__ = "nervum_projects"

    id         = Column(String(255), primary_key=True)
    name       = Column(String(255), nullable=False, index=True)
    slug       = Column(String(255), nullable=True)
    status     = Column(String(50),  nullable=True, index=True)
    labels     = Column(JSON,        nullable=True)
    raw        = Column(JSON,        nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class NervumLogicalPortRow(Base):
    """Replica of Nervum logical_port objects."""

    __tablename__ = "nervum_logical_ports"

    id         = Column(String(255), primary_key=True)
    name       = Column(String(255), nullable=False, index=True)
    network_id = Column(String(255), nullable=True, index=True)
    project_id = Column(String(255), nullable=True, index=True)
    status     = Column(String(50),  nullable=True, index=True)  # pending|active|detached
    mac        = Column(String(50),  nullable=True)
    ip_address = Column(String(100), nullable=True)
    labels     = Column(JSON,        nullable=True)
    raw        = Column(JSON,        nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class NervumSecurityGroupRow(Base):
    """Replica of Nervum security_group objects."""

    __tablename__ = "nervum_security_groups"

    id         = Column(String(255), primary_key=True)
    name       = Column(String(255), nullable=False, index=True)
    project_id = Column(String(255), nullable=True, index=True)
    rules      = Column(JSON,        nullable=True)
    labels     = Column(JSON,        nullable=True)
    raw        = Column(JSON,        nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class NervumAddressPoolRow(Base):
    """Replica of Nervum address_pool objects."""

    __tablename__ = "nervum_address_pools"

    id         = Column(String(255), primary_key=True)
    name       = Column(String(255), nullable=False, index=True)
    project_id = Column(String(255), nullable=True, index=True)
    cidr       = Column(String(100), nullable=True)
    labels     = Column(JSON,        nullable=True)
    raw        = Column(JSON,        nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class NervumServiceObjectRow(Base):
    """Replica of Nervum service_object objects."""

    __tablename__ = "nervum_service_objects"

    id         = Column(String(255), primary_key=True)
    name       = Column(String(255), nullable=False, index=True)
    project_id = Column(String(255), nullable=True, index=True)
    protocol   = Column(String(50),  nullable=True)   # tcp|udp|icmp|any
    port_range = Column(String(100), nullable=True)
    labels     = Column(JSON,        nullable=True)
    raw        = Column(JSON,        nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class NervumQosPolicyRow(Base):
    """Replica of Nervum qos_policy objects."""

    __tablename__ = "nervum_qos_policies"

    id         = Column(String(255), primary_key=True)
    name       = Column(String(255), nullable=False, index=True)
    project_id = Column(String(255), nullable=True, index=True)
    labels     = Column(JSON,        nullable=True)
    raw        = Column(JSON,        nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class NervumSecurityPolicyRow(Base):
    """Replica of Nervum security_policy objects."""

    __tablename__ = "nervum_security_policies"

    id         = Column(String(255), primary_key=True)
    name       = Column(String(255), nullable=False, index=True)
    project_id = Column(String(255), nullable=True, index=True)
    status     = Column(String(50),  nullable=True, index=True)  # draft|compiled|applied|failed
    labels     = Column(JSON,        nullable=True)
    raw        = Column(JSON,        nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class NervumTrunkPortRow(Base):
    """Replica of Nervum trunk_port objects."""

    __tablename__ = "nervum_trunk_ports"

    id         = Column(String(255), primary_key=True)
    name       = Column(String(255), nullable=False, index=True)
    project_id = Column(String(255), nullable=True, index=True)
    labels     = Column(JSON,        nullable=True)
    raw        = Column(JSON,        nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class NervumRouterRow(Base):
    """Replica of Nervum router objects."""

    __tablename__ = "nervum_routers"

    id         = Column(String(255), primary_key=True)
    name       = Column(String(255), nullable=False, index=True)
    project_id = Column(String(255), nullable=True, index=True)
    status     = Column(String(50),  nullable=True, index=True)  # build|active|down|error
    mode       = Column(String(50),  nullable=True)              # ipv6: off|slaac|stateful|stateless
    labels     = Column(JSON,        nullable=True)
    raw        = Column(JSON,        nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class NervumFloatingIpRow(Base):
    """Replica of Nervum floating_ip objects."""

    __tablename__ = "nervum_floating_ips"

    id         = Column(String(255), primary_key=True)
    project_id = Column(String(255), nullable=True, index=True)
    router_id  = Column(String(255), nullable=True, index=True)
    address    = Column(String(100), nullable=True)
    status     = Column(String(50),  nullable=True, index=True)  # down|active|error
    raw        = Column(JSON,        nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class NervumBgpPeerRow(Base):
    """Replica of Nervum bgp_peer objects."""

    __tablename__ = "nervum_bgp_peers"

    id         = Column(String(255), primary_key=True)
    router_id  = Column(String(255), nullable=True, index=True)
    project_id = Column(String(255), nullable=True, index=True)
    peer_ip    = Column(String(100), nullable=True)
    remote_asn = Column(Integer,     nullable=True)
    labels     = Column(JSON,        nullable=True)
    raw        = Column(JSON,        nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class NervumGatewayBondRow(Base):
    """Replica of Nervum gateway_bond objects."""

    __tablename__ = "nervum_gateway_bonds"

    id         = Column(String(255), primary_key=True)
    name       = Column(String(255), nullable=False, index=True)
    project_id = Column(String(255), nullable=True, index=True)
    mode       = Column(String(50),  nullable=True)   # none|active_backup|lacp
    labels     = Column(JSON,        nullable=True)
    raw        = Column(JSON,        nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class NervumLoadBalancerRow(Base):
    """Replica of Nervum load_balancer objects."""

    __tablename__ = "nervum_load_balancers"

    id         = Column(String(255), primary_key=True)
    name       = Column(String(255), nullable=False, index=True)
    project_id = Column(String(255), nullable=True, index=True)
    router_id  = Column(String(255), nullable=True, index=True)
    status     = Column(String(50),  nullable=True, index=True)  # build|active|down|error
    labels     = Column(JSON,        nullable=True)
    raw        = Column(JSON,        nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class NervumApplyScheduleRow(Base):
    """Replica of Nervum apply_schedule objects."""

    __tablename__ = "nervum_apply_schedules"

    id         = Column(String(255), primary_key=True)
    name       = Column(String(255), nullable=False, index=True)
    project_id = Column(String(255), nullable=True, index=True)
    status     = Column(String(50),  nullable=True, index=True)  # active|paused|error
    labels     = Column(JSON,        nullable=True)
    raw        = Column(JSON,        nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class NervumMirrorSessionRow(Base):
    """Replica of Nervum mirror_session objects."""

    __tablename__ = "nervum_mirror_sessions"

    id         = Column(String(255), primary_key=True)
    name       = Column(String(255), nullable=False, index=True)
    project_id = Column(String(255), nullable=True, index=True)
    status     = Column(String(50),  nullable=True, index=True)  # active|inactive|error
    labels     = Column(JSON,        nullable=True)
    raw        = Column(JSON,        nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class NervumVpnTunnelRow(Base):
    """Replica of Nervum vpn_tunnel objects."""

    __tablename__ = "nervum_vpn_tunnels"

    id         = Column(String(255), primary_key=True)
    name       = Column(String(255), nullable=False, index=True)
    project_id = Column(String(255), nullable=True, index=True)
    protocol   = Column(String(50),  nullable=True)              # wireguard|ipsec
    status     = Column(String(50),  nullable=True, index=True)  # build|active|down|error
    labels     = Column(JSON,        nullable=True)
    raw        = Column(JSON,        nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class VmSdnPortRow(Base):
    """T7: tracks the Nervum LogicalPort bound to a VM NIC.

    One row per VM per NIC — keyed by (platform_id, vm_name).
    Deleted when the VM is destroyed.
    """

    __tablename__ = "vm_sdn_ports"

    id          = Column(GUID(),      primary_key=True, default=uuid.uuid4)
    platform_id = Column(GUID(),      ForeignKey("platforms.id", ondelete="CASCADE"), nullable=False)
    vm_name     = Column(String(255), nullable=False, index=True)
    port_id     = Column(String(255), nullable=False, index=True)
    network_id  = Column(String(255), nullable=True)
    project_id  = Column(String(255), nullable=True)
    mac         = Column(String(50),  nullable=True)
    ip_address  = Column(String(100), nullable=True)
    created_at  = Column(DateTime,    default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("platform_id", "vm_name", name="uq_vm_sdn_port"),
    )


class NervumEventQuarantineRow(Base):
    """Quarantine log for unrecognised or future-schema Nervum events."""

    __tablename__ = "nervum_event_quarantine"

    id             = Column(Integer,     primary_key=True, autoincrement=True)
    event_id       = Column(Integer,     nullable=True, index=True)
    schema_version = Column(Integer,     nullable=True)
    event_type     = Column(String(255), nullable=True)
    resource_type  = Column(String(100), nullable=True)
    resource_id    = Column(String(255), nullable=True)
    raw            = Column(JSON,        nullable=True)
    received_at    = Column(DateTime,    default=datetime.utcnow, nullable=False, index=True)
