# SPDX-License-Identifier: MIT
"""Initial schema: create tables for all models."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _uuid_col(name: str, **kw):
    """UUID primary/foreign key column, cross-database."""
    if _is_pg():
        return sa.Column(name, postgresql.UUID(as_uuid=True), **kw)
    return sa.Column(name, sa.String(36), **kw)


def _enum_col(name: str, *values: str, enum_name: str, **kw):
    """ENUM column: native ENUM on PostgreSQL, String on SQLite."""
    if _is_pg():
        return sa.Column(
            name,
            postgresql.ENUM(*values, name=enum_name, create_type=False),
            **kw,
        )
    return sa.Column(name, sa.String(50), **kw)


def _json_col(name: str, **kw):
    """JSONB on PostgreSQL, JSON on SQLite."""
    if _is_pg():
        return sa.Column(name, postgresql.JSONB(astext_type=sa.Text()), **kw)
    return sa.Column(name, sa.JSON(), **kw)


def upgrade() -> None:
    # PostgreSQL-only: create native ENUM types
    if _is_pg():
        enums = {
            "userrole": ("admin", "operator", "viewer"),
            "authmethodenum": ("password", "private_key"),
            "tasktypeenum": ("deploy", "run_command"),
            "taskstatusenum": ("pending", "running", "success", "failed"),
            "automationexecutionenum": ("command", "script"),
            "automationtriggerenum": ("manual", "cron", "github_push", "webhook"),
        }
        for name, values in enums.items():
            quoted = ", ".join(f"'{v}'" for v in values)
            op.execute(
                sa.text(
                    f"DO $$ BEGIN CREATE TYPE {name} AS ENUM ({quoted}); "
                    "EXCEPTION WHEN duplicate_object THEN null; END $$;"
                )
            )

    op.create_table(
        "ssh_keys",
        _uuid_col("id", nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("encrypted_private_key", sa.LargeBinary(), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ssh_keys_name", "ssh_keys", ["name"], unique=False)

    op.create_table(
        "users",
        _uuid_col("id", nullable=False),
        sa.Column("username", sa.String(length=150), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        _enum_col("role", "admin", "operator", "viewer", enum_name="userrole", nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("last_login", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_role", "users", ["role"], unique=False)
    op.create_index("ix_users_is_active", "users", ["is_active"], unique=False)

    op.create_table(
        "platforms",
        _uuid_col("id", nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=False),
        _enum_col("auth_method", "password", "private_key", enum_name="authmethodenum", nullable=False),
        sa.Column("encrypted_password", sa.LargeBinary(), nullable=True),
        sa.Column("encrypted_private_key", sa.LargeBinary(), nullable=True),
        _uuid_col("ssh_key_id", nullable=True),
        sa.Column("known_host_fingerprint", sa.String(length=255), nullable=True),
        sa.Column("system_info", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["ssh_key_id"], ["ssh_keys.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "job_tasks",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        _json_col("payload", nullable=True),
        sa.Column("idempotency_key", sa.String(), nullable=True),
        sa.Column("timeout_s", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_job_tasks_status", "job_tasks", ["status"], unique=False)
    op.create_index("ix_job_tasks_scheduled_for", "job_tasks", ["scheduled_for"], unique=False)

    op.create_table(
        "task_runs",
        _uuid_col("id", nullable=False),
        _enum_col("type", "deploy", "run_command", enum_name="tasktypeenum", nullable=False),
        _uuid_col("platform_id", nullable=True),
        _enum_col("status", "pending", "running", "success", "failed", enum_name="taskstatusenum", nullable=False),
        sa.Column("result_location", sa.String(length=512), nullable=True),
        sa.Column("stdout", sa.Text(), nullable=True),
        sa.Column("stderr", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("task_metadata", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["platform_id"], ["platforms.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_runs_type", "task_runs", ["type"], unique=False)
    op.create_index("ix_task_runs_status", "task_runs", ["status"], unique=False)

    op.create_table(
        "scripts",
        _uuid_col("id", nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("language", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "automation_jobs",
        _uuid_col("id", nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        _enum_col("execution_type", "command", "script", enum_name="automationexecutionenum", nullable=False),
        sa.Column("command", sa.Text(), nullable=True),
        _uuid_col("script_id", nullable=True),
        _enum_col("trigger_type", "manual", "cron", "github_push", "webhook", enum_name="automationtriggerenum", nullable=False),
        sa.Column("cron_expression", sa.String(length=255), nullable=True),
        sa.Column("repository_url", sa.String(length=512), nullable=True),
        sa.Column("repository_branch", sa.String(length=120), nullable=True),
        sa.Column("webhook_secret", sa.String(length=255), nullable=True),
        sa.Column("environment", sa.JSON(), nullable=True),
        sa.Column("parameters", sa.JSON(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("notification_settings", sa.JSON(), nullable=True),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("retry_delay_seconds", sa.Integer(), nullable=False),
        sa.Column("concurrency_limit", sa.Integer(), nullable=True),
        sa.Column("require_approval", sa.Boolean(), nullable=False),
        sa.Column("run_on_all_platforms", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("next_run_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["script_id"], ["scripts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "automation_job_platforms",
        _uuid_col("id", nullable=False),
        _uuid_col("job_id", nullable=False),
        _uuid_col("platform_id", nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["automation_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["platform_id"], ["platforms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "platform_id", name="uq_automation_job_platform"),
    )

    op.create_table(
        "audit_logs",
        _uuid_col("id", nullable=False),
        sa.Column("user", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=255), nullable=False),
        sa.Column("object_type", sa.String(length=100), nullable=False),
        sa.Column("object_id", sa.String(length=255), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_user", "audit_logs", ["user"], unique=False)
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"], unique=False)
    op.create_index("ix_audit_logs_object_type", "audit_logs", ["object_type"], unique=False)
    op.create_index("ix_audit_logs_object_id", "audit_logs", ["object_id"], unique=False)
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_logs_timestamp", table_name="audit_logs")
    op.drop_index("ix_audit_logs_object_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_object_type", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_user", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_table("automation_job_platforms")
    op.drop_table("automation_jobs")
    op.drop_table("scripts")
    op.drop_index("ix_task_runs_status", table_name="task_runs")
    op.drop_index("ix_task_runs_type", table_name="task_runs")
    op.drop_table("task_runs")
    op.drop_table("platforms")
    op.drop_index("ix_users_is_active", table_name="users")
    op.drop_index("ix_users_role", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_ssh_keys_name", table_name="ssh_keys")
    op.drop_table("ssh_keys")
    op.drop_index("ix_job_tasks_status", table_name="job_tasks")
    op.drop_index("ix_job_tasks_scheduled_for", table_name="job_tasks")
    op.drop_table("job_tasks")

    if _is_pg():
        for name in (
            "automationtriggerenum",
            "automationexecutionenum",
            "taskstatusenum",
            "tasktypeenum",
            "authmethodenum",
            "userrole",
        ):
            op.execute(sa.text(f"DROP TYPE IF EXISTS {name} CASCADE"))
