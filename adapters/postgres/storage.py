# SPDX-License-Identifier: MIT
"""SQLAlchemy implementation of the Storage interface."""
from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional

from sqlalchemy.orm import Session

from adapters.postgres.orm_models import (
    AuditLogRow,
    AutomationJobPlatformRow,
    AutomationJobRow,
    PlatformRow,
    ScriptRow,
    SSHKeyRow,
    TaskRunRow,
    UserRow,
)
from adapters.postgres.session import SessionLocal
from core.domain.enums import (
    AuthMethod,
    ExecutionType,
    TaskStatus,
    TaskType,
    TriggerType,
    UserRole,
)
from core.domain.models import (
    AuditLog,
    AutomationJob,
    Platform,
    Script,
    SSHKey,
    TaskRun,
    User,
)


# ── Mapping helpers ────────────────────────────────────────────────────────

def _map_user(row: UserRow) -> User:
    return User(
        id=str(row.id),
        username=row.username,
        hashed_password=row.hashed_password,
        role=UserRole(row.role.value if hasattr(row.role, "value") else row.role),
        is_active=row.is_active,
        email=row.email,
        created_at=row.created_at,
        updated_at=row.updated_at,
        last_login=row.last_login,
    )


def _map_key(row: SSHKeyRow) -> SSHKey:
    return SSHKey(
        id=str(row.id),
        name=row.name,
        public_key=row.public_key,
        created_at=row.created_at,
        created_by=row.created_by,
        has_private_key=bool(row.encrypted_private_key),
    )


def _map_platform(row: PlatformRow) -> Platform:
    return Platform(
        id=str(row.id),
        name=row.name,
        host=row.host,
        port=row.port,
        username=row.username,
        auth_method=AuthMethod(row.auth_method.value if hasattr(row.auth_method, "value") else row.auth_method),
        ssh_key_id=str(row.ssh_key_id) if row.ssh_key_id else None,
        known_host_fingerprint=row.known_host_fingerprint,
        system_info=row.system_info,
        created_at=row.created_at,
    )


def _map_task_run(row: TaskRunRow) -> TaskRun:
    return TaskRun(
        id=str(row.id),
        type=TaskType(row.type.value if hasattr(row.type, "value") else row.type),
        status=TaskStatus(row.status.value if hasattr(row.status, "value") else row.status),
        platform_id=str(row.platform_id) if row.platform_id else None,
        result_location=row.result_location,
        stdout=row.stdout,
        stderr=row.stderr,
        error_message=row.error_message,
        pyjobkit_job_id=row.pyjobkit_job_id,
        task_metadata=row.task_metadata,
        started_at=row.started_at,
        finished_at=row.finished_at,
        created_at=row.created_at,
    )


def _map_script(row: ScriptRow) -> Script:
    return Script(
        id=str(row.id),
        name=row.name,
        language=row.language,
        content=row.content,
        description=row.description,
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _map_automation(row: AutomationJobRow) -> AutomationJob:
    return AutomationJob(
        id=str(row.id),
        name=row.name,
        description=row.description,
        execution_type=ExecutionType(row.execution_type.value if hasattr(row.execution_type, "value") else row.execution_type),
        command=row.command,
        script_id=str(row.script_id) if row.script_id else None,
        trigger_type=TriggerType(row.trigger_type.value if hasattr(row.trigger_type, "value") else row.trigger_type),
        cron_expression=row.cron_expression,
        repository_url=row.repository_url,
        repository_branch=row.repository_branch,
        webhook_secret=row.webhook_secret,
        environment=row.environment,
        parameters=row.parameters,
        tags=row.tags,
        notification_settings=row.notification_settings,
        timeout_seconds=row.timeout_seconds,
        max_retries=row.max_retries,
        retry_delay_seconds=row.retry_delay_seconds,
        concurrency_limit=row.concurrency_limit,
        require_approval=row.require_approval,
        run_on_all_platforms=row.run_on_all_platforms,
        notes=row.notes,
        is_enabled=row.is_enabled,
        created_by=row.created_by,
        last_run_at=row.last_run_at,
        next_run_at=row.next_run_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        platform_ids=[str(lnk.platform_id) for lnk in (row.platform_links or [])],
    )


def _map_audit(row: AuditLogRow) -> AuditLog:
    return AuditLog(
        id=str(row.id),
        user=row.user,
        action=row.action,
        object_type=row.object_type,
        object_id=row.object_id,
        meta=row.meta,
        timestamp=row.timestamp,
    )


# ── Storage implementation ─────────────────────────────────────────────────

class SQLStorage:
    """Implements the Storage protocol using SQLAlchemy sessions."""

    @contextmanager
    def _db(self) -> Generator[Session, None, None]:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    # ── Users ──────────────────────────────────────────────────────────────

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        with self._db() as db:
            row = db.query(UserRow).filter(UserRow.id == user_id).first()
            return _map_user(row) if row else None

    def get_user_by_username(self, username: str) -> Optional[User]:
        with self._db() as db:
            row = db.query(UserRow).filter(UserRow.username == username).first()
            return _map_user(row) if row else None

    def list_users(self, limit: int = 50, offset: int = 0) -> List[User]:
        with self._db() as db:
            rows = db.query(UserRow).order_by(UserRow.created_at.desc()).offset(offset).limit(limit).all()
            return [_map_user(r) for r in rows]

    def count_users(self) -> int:
        with self._db() as db:
            return db.query(UserRow).count()

    def create_user(self, **fields: Any) -> User:
        with self._db() as db:
            row = UserRow(**fields)
            db.add(row)
            db.commit()
            db.refresh(row)
            return _map_user(row)

    def update_user(self, user_id: str, **fields: Any) -> Optional[User]:
        with self._db() as db:
            row = db.query(UserRow).filter(UserRow.id == user_id).first()
            if not row:
                return None
            for k, v in fields.items():
                setattr(row, k, v)
            db.commit()
            db.refresh(row)
            return _map_user(row)

    def delete_user(self, user_id: str) -> bool:
        with self._db() as db:
            row = db.query(UserRow).filter(UserRow.id == user_id).first()
            if not row:
                return False
            db.delete(row)
            db.commit()
            return True

    # ── SSH Keys ───────────────────────────────────────────────────────────

    def get_key_by_id(self, key_id: str) -> Optional[SSHKey]:
        with self._db() as db:
            row = db.query(SSHKeyRow).filter(SSHKeyRow.id == key_id).first()
            return _map_key(row) if row else None

    def list_keys(self, limit: int = 50, offset: int = 0) -> List[SSHKey]:
        with self._db() as db:
            rows = db.query(SSHKeyRow).order_by(SSHKeyRow.created_at.desc()).offset(offset).limit(limit).all()
            return [_map_key(r) for r in rows]

    def count_keys(self) -> int:
        with self._db() as db:
            return db.query(SSHKeyRow).count()

    def create_key(self, **fields: Any) -> SSHKey:
        with self._db() as db:
            row = SSHKeyRow(**fields)
            db.add(row)
            db.commit()
            db.refresh(row)
            return _map_key(row)

    def delete_key(self, key_id: str) -> bool:
        with self._db() as db:
            row = db.query(SSHKeyRow).filter(SSHKeyRow.id == key_id).first()
            if not row:
                return False
            db.delete(row)
            db.commit()
            return True

    # ── Platforms ──────────────────────────────────────────────────────────

    def get_platform_by_id(self, platform_id: str) -> Optional[Platform]:
        with self._db() as db:
            row = db.query(PlatformRow).filter(PlatformRow.id == platform_id).first()
            return _map_platform(row) if row else None

    def list_platforms(self, limit: int = 50, offset: int = 0) -> List[Platform]:
        with self._db() as db:
            rows = db.query(PlatformRow).order_by(PlatformRow.created_at.desc()).offset(offset).limit(limit).all()
            return [_map_platform(r) for r in rows]

    def count_platforms(self) -> int:
        with self._db() as db:
            return db.query(PlatformRow).count()

    def create_platform(self, **fields: Any) -> Platform:
        with self._db() as db:
            row = PlatformRow(**fields)
            db.add(row)
            db.commit()
            db.refresh(row)
            return _map_platform(row)

    def update_platform(self, platform_id: str, **fields: Any) -> Optional[Platform]:
        with self._db() as db:
            row = db.query(PlatformRow).filter(PlatformRow.id == platform_id).first()
            if not row:
                return None
            for k, v in fields.items():
                setattr(row, k, v)
            db.commit()
            db.refresh(row)
            return _map_platform(row)

    def delete_platform(self, platform_id: str) -> bool:
        with self._db() as db:
            row = db.query(PlatformRow).filter(PlatformRow.id == platform_id).first()
            if not row:
                return False
            db.delete(row)
            db.commit()
            return True

    # ── Task Runs ──────────────────────────────────────────────────────────

    def get_task_run_by_id(self, task_run_id: str) -> Optional[TaskRun]:
        with self._db() as db:
            row = db.query(TaskRunRow).filter(TaskRunRow.id == task_run_id).first()
            return _map_task_run(row) if row else None

    def list_task_runs(
        self,
        platform_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[TaskRun]:
        with self._db() as db:
            q = db.query(TaskRunRow)
            if platform_id:
                q = q.filter(TaskRunRow.platform_id == platform_id)
            rows = q.order_by(TaskRunRow.created_at.desc()).offset(offset).limit(limit).all()
            return [_map_task_run(r) for r in rows]

    def count_task_runs(self, platform_id: Optional[str] = None) -> int:
        with self._db() as db:
            q = db.query(TaskRunRow)
            if platform_id:
                q = q.filter(TaskRunRow.platform_id == platform_id)
            return q.count()

    def create_task_run(self, **fields: Any) -> TaskRun:
        with self._db() as db:
            row = TaskRunRow(**fields)
            db.add(row)
            db.commit()
            db.refresh(row)
            return _map_task_run(row)

    def update_task_run(self, task_run_id: str, **fields: Any) -> Optional[TaskRun]:
        with self._db() as db:
            row = db.query(TaskRunRow).filter(TaskRunRow.id == task_run_id).first()
            if not row:
                return None
            for k, v in fields.items():
                setattr(row, k, v)
            db.commit()
            db.refresh(row)
            return _map_task_run(row)

    # ── Scripts ────────────────────────────────────────────────────────────

    def get_script_by_id(self, script_id: str) -> Optional[Script]:
        with self._db() as db:
            row = db.query(ScriptRow).filter(ScriptRow.id == script_id).first()
            return _map_script(row) if row else None

    def list_scripts(self, limit: int = 50, offset: int = 0) -> List[Script]:
        with self._db() as db:
            rows = db.query(ScriptRow).order_by(ScriptRow.created_at.desc()).offset(offset).limit(limit).all()
            return [_map_script(r) for r in rows]

    def count_scripts(self) -> int:
        with self._db() as db:
            return db.query(ScriptRow).count()

    def create_script(self, **fields: Any) -> Script:
        with self._db() as db:
            row = ScriptRow(**fields)
            db.add(row)
            db.commit()
            db.refresh(row)
            return _map_script(row)

    def update_script(self, script_id: str, **fields: Any) -> Optional[Script]:
        with self._db() as db:
            row = db.query(ScriptRow).filter(ScriptRow.id == script_id).first()
            if not row:
                return None
            for k, v in fields.items():
                setattr(row, k, v)
            db.commit()
            db.refresh(row)
            return _map_script(row)

    def delete_script(self, script_id: str) -> bool:
        with self._db() as db:
            row = db.query(ScriptRow).filter(ScriptRow.id == script_id).first()
            if not row:
                return False
            db.delete(row)
            db.commit()
            return True

    # ── Automation Jobs ────────────────────────────────────────────────────

    def get_automation_by_id(self, automation_id: str) -> Optional[AutomationJob]:
        with self._db() as db:
            row = db.query(AutomationJobRow).filter(AutomationJobRow.id == automation_id).first()
            return _map_automation(row) if row else None

    def list_automations(self, limit: int = 50, offset: int = 0) -> List[AutomationJob]:
        with self._db() as db:
            rows = db.query(AutomationJobRow).order_by(AutomationJobRow.created_at.desc()).offset(offset).limit(limit).all()
            return [_map_automation(r) for r in rows]

    def count_automations(self) -> int:
        with self._db() as db:
            return db.query(AutomationJobRow).count()

    def create_automation(self, **fields: Any) -> AutomationJob:
        platform_ids = fields.pop("platform_ids", [])
        with self._db() as db:
            row = AutomationJobRow(**fields)
            db.add(row)
            db.flush()
            for pid in platform_ids:
                db.add(AutomationJobPlatformRow(job_id=row.id, platform_id=pid))
            db.commit()
            db.refresh(row)
            return _map_automation(row)

    def update_automation(self, automation_id: str, **fields: Any) -> Optional[AutomationJob]:
        platform_ids = fields.pop("platform_ids", None)
        with self._db() as db:
            row = db.query(AutomationJobRow).filter(AutomationJobRow.id == automation_id).first()
            if not row:
                return None
            for k, v in fields.items():
                setattr(row, k, v)
            if platform_ids is not None:
                db.query(AutomationJobPlatformRow).filter(
                    AutomationJobPlatformRow.job_id == row.id
                ).delete()
                for pid in platform_ids:
                    db.add(AutomationJobPlatformRow(job_id=row.id, platform_id=pid))
            db.commit()
            db.refresh(row)
            return _map_automation(row)

    def delete_automation(self, automation_id: str) -> bool:
        with self._db() as db:
            row = db.query(AutomationJobRow).filter(AutomationJobRow.id == automation_id).first()
            if not row:
                return False
            db.delete(row)
            db.commit()
            return True

    # ── Audit Logs ─────────────────────────────────────────────────────────

    def create_audit_log(self, **fields: Any) -> AuditLog:
        with self._db() as db:
            row = AuditLogRow(**fields)
            db.add(row)
            db.commit()
            db.refresh(row)
            return _map_audit(row)

    def list_audit_logs(
        self,
        object_type: Optional[str] = None,
        user: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[AuditLog]:
        with self._db() as db:
            q = db.query(AuditLogRow)
            if object_type:
                q = q.filter(AuditLogRow.object_type == object_type)
            if user:
                q = q.filter(AuditLogRow.user == user)
            rows = q.order_by(AuditLogRow.timestamp.desc()).offset(offset).limit(limit).all()
            return [_map_audit(r) for r in rows]

    def count_audit_logs(
        self,
        object_type: Optional[str] = None,
        user: Optional[str] = None,
    ) -> int:
        with self._db() as db:
            q = db.query(AuditLogRow)
            if object_type:
                q = q.filter(AuditLogRow.object_type == object_type)
            if user:
                q = q.filter(AuditLogRow.user == user)
            return q.count()
