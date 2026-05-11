# SPDX-License-Identifier: MIT
"""Automation jobs API endpoints."""
import hmac
import hashlib
import uuid
from typing import List, Optional

from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route, Router

from app.audit import log_audit
from app.db import get_db
from app.models import (
    AutomationExecutionEnum,
    AutomationJob,
    AutomationJobPlatform,
    AutomationTriggerEnum,
    Platform,
    UserRole,
)
from ports.api.schemas import (
    AutomationJobCreate,
    AutomationJobResponse,
    AutomationJobTargetResponse,
    AutomationJobUpdate,
    MessageResponse,
)
from app.rbac import ALL_ROLES, get_request_user, require_roles

router = Router()


def _get_db_session() -> Session:
    """Return a database session using the shared dependency."""

    return next(get_db())


def _enum_value(value, default: str) -> str:
    """Normalize enum or string values to plain strings."""

    if value is None:
        return default
    if isinstance(value, str):
        return value
    return value.value


def _build_response(job: AutomationJob) -> dict:
    """Convert ORM object into serializable schema."""

    targets = [
        AutomationJobTargetResponse(
            platform_id=link.platform_id,
            platform_name=link.platform.name if link.platform else None,
        )
        for link in job.platform_links
    ]
    schema = AutomationJobResponse(
        id=job.id,
        name=job.name,
        description=job.description,
        execution_type=_enum_value(job.execution_type, AutomationExecutionEnum.COMMAND.value),
        command=job.command,
        script_id=job.script_id,
        trigger_type=_enum_value(job.trigger_type, AutomationTriggerEnum.MANUAL.value),
        cron_expression=job.cron_expression,
        repository_url=job.repository_url,
        repository_branch=job.repository_branch,
        webhook_secret=job.webhook_secret,
        environment=job.environment or {},
        parameters=job.parameters or {},
        tags=job.tags or [],
        notification_settings=job.notification_settings or {},
        timeout_seconds=job.timeout_seconds,
        max_retries=job.max_retries,
        retry_delay_seconds=job.retry_delay_seconds,
        concurrency_limit=job.concurrency_limit,
        require_approval=job.require_approval,
        run_on_all_platforms=job.run_on_all_platforms,
        notes=job.notes,
        is_enabled=job.is_enabled,
        target_platform_ids=[link.platform_id for link in job.platform_links],
        targets=targets,
        created_by=job.created_by,
        last_run_at=job.last_run_at,
        next_run_at=job.next_run_at,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )
    return schema.model_dump(mode="json")


def _clean_tags(tags: Optional[List[str]]) -> Optional[List[str]]:
    """Normalize tag lists by trimming whitespace and removing empties."""

    if not tags:
        return None
    cleaned = [tag.strip() for tag in tags if isinstance(tag, str) and tag.strip()]
    return cleaned or None


@require_roles(*ALL_ROLES)
async def list_jobs(request: Request) -> JSONResponse:
    """Return all automation jobs sorted by creation date."""

    db: Session = _get_db_session()
    try:
        jobs: List[AutomationJob] = (
            db.query(AutomationJob)
            .order_by(AutomationJob.created_at.desc())
            .all()
        )
        payload = [_build_response(job) for job in jobs]
        return JSONResponse(payload)
    finally:
        db.close()


@require_roles(UserRole.ADMIN, UserRole.OPERATOR)
async def create_job(request: Request) -> JSONResponse:
    """Create a new automation job definition."""

    db: Session = _get_db_session()
    try:
        data = await request.json()
        payload = AutomationJobCreate(**data)

        if not payload.run_on_all_platforms:
            requested_ids = set(payload.target_platform_ids)
            if len(requested_ids) != len(payload.target_platform_ids):
                return JSONResponse({"error": "Duplicate platform IDs provided"}, status_code=400)
            platforms = (
                db.query(Platform)
                .filter(Platform.id.in_(list(requested_ids)))
                .all()
            )
            if len(platforms) != len(requested_ids):
                return JSONResponse({"error": "One or more platform IDs are invalid"}, status_code=400)
        else:
            platforms = []

        user = get_request_user(request)

        cron_expr = payload.cron_expression.strip() if payload.cron_expression else None
        next_run_at = None
        if AutomationTriggerEnum(payload.trigger_type) == AutomationTriggerEnum.CRON and cron_expr:
            try:
                from app.scheduler import calc_next_run
                next_run_at = calc_next_run(cron_expr).replace(tzinfo=None)
            except Exception:
                pass

        job = AutomationJob(
            id=uuid.uuid4(),
            name=payload.name.strip(),
            description=payload.description.strip() if payload.description else None,
            execution_type=AutomationExecutionEnum(payload.execution_type),
            command=payload.command.strip() if payload.command else None,
            script_id=payload.script_id,
            trigger_type=AutomationTriggerEnum(payload.trigger_type),
            cron_expression=cron_expr,
            repository_url=payload.repository_url.strip() if payload.repository_url else None,
            repository_branch=payload.repository_branch.strip() if payload.repository_branch else None,
            webhook_secret=payload.webhook_secret.strip() if payload.webhook_secret else None,
            environment=payload.environment or None,
            parameters=payload.parameters or None,
            tags=_clean_tags(payload.tags),
            notification_settings=payload.notification_settings or None,
            timeout_seconds=payload.timeout_seconds,
            max_retries=payload.max_retries,
            retry_delay_seconds=payload.retry_delay_seconds,
            concurrency_limit=payload.concurrency_limit,
            require_approval=payload.require_approval,
            run_on_all_platforms=payload.run_on_all_platforms,
            notes=payload.notes.strip() if payload.notes else None,
            is_enabled=payload.is_enabled,
            created_by=user.username if user else "system",
            next_run_at=next_run_at,
        )

        db.add(job)
        db.flush()

        if not payload.run_on_all_platforms:
            for platform in platforms:
                db.add(
                    AutomationJobPlatform(
                        id=uuid.uuid4(),
                        job_id=job.id,
                        platform_id=platform.id,
                    )
                )

        db.commit()
        db.refresh(job)

        log_audit(
            db,
            user=user.username if user else "system",
            action="create",
            object_type="automation_job",
            object_id=str(job.id),
            meta={"name": job.name, "trigger_type": job.trigger_type},
        )

        return JSONResponse(_build_response(job), status_code=201)
    except Exception as exc:  # pragma: no cover - safety net consistent with other endpoints
        db.rollback()
        return JSONResponse({"error": str(exc)}, status_code=400)
    finally:
        db.close()


@require_roles(*ALL_ROLES)
async def get_job(request: Request) -> JSONResponse:
    """Return a single automation job."""

    job_id = request.path_params["job_id"]
    db: Session = _get_db_session()
    try:
        job = db.query(AutomationJob).filter(AutomationJob.id == job_id).first()
        if not job:
            return JSONResponse({"error": "Automation job not found"}, status_code=404)
        return JSONResponse(_build_response(job))
    finally:
        db.close()


@require_roles(UserRole.ADMIN, UserRole.OPERATOR)
async def update_job(request: Request) -> JSONResponse:
    """Update an existing automation job."""

    job_id = request.path_params["job_id"]
    db: Session = _get_db_session()
    try:
        payload = await request.json()
        update_data = AutomationJobUpdate(**payload)

        job = db.query(AutomationJob).filter(AutomationJob.id == job_id).first()
        if not job:
            return JSONResponse({"error": "Automation job not found"}, status_code=404)

        user = get_request_user(request)

        data = update_data.model_dump(exclude_unset=True)

        if "name" in data and data["name"]:
            job.name = data["name"].strip()
        if "description" in data:
            job.description = data["description"].strip() if data["description"] else None
        if "execution_type" in data:
            job.execution_type = AutomationExecutionEnum(data["execution_type"])
        if "command" in data:
            job.command = data["command"].strip() if data["command"] else None
        if "script_id" in data:
            job.script_id = data["script_id"]
        if "trigger_type" in data:
            job.trigger_type = AutomationTriggerEnum(data["trigger_type"])
        if "cron_expression" in data:
            job.cron_expression = data["cron_expression"].strip() if data["cron_expression"] else None
            if job.cron_expression and job.trigger_type in (AutomationTriggerEnum.CRON, "cron"):
                try:
                    from app.scheduler import calc_next_run
                    job.next_run_at = calc_next_run(job.cron_expression).replace(tzinfo=None)
                except Exception:
                    pass
        if "repository_url" in data:
            job.repository_url = data["repository_url"].strip() if data["repository_url"] else None
        if "repository_branch" in data:
            job.repository_branch = data["repository_branch"].strip() if data["repository_branch"] else None
        if "webhook_secret" in data:
            job.webhook_secret = data["webhook_secret"].strip() if data["webhook_secret"] else None
        if "environment" in data:
            job.environment = data["environment"] or None
        if "parameters" in data:
            job.parameters = data["parameters"] or None
        if "tags" in data:
            job.tags = _clean_tags(data["tags"])
        if "notification_settings" in data:
            job.notification_settings = data["notification_settings"] or None
        if "timeout_seconds" in data:
            job.timeout_seconds = data["timeout_seconds"]
        if "max_retries" in data:
            job.max_retries = data["max_retries"]
        if "retry_delay_seconds" in data:
            job.retry_delay_seconds = data["retry_delay_seconds"]
        if "concurrency_limit" in data:
            job.concurrency_limit = data["concurrency_limit"]
        if "require_approval" in data:
            job.require_approval = data["require_approval"]
        if "notes" in data:
            job.notes = data["notes"].strip() if data["notes"] else None
        if "is_enabled" in data:
            job.is_enabled = data["is_enabled"]
        run_all_updated = False
        new_targets_set = None
        if "run_on_all_platforms" in data:
            job.run_on_all_platforms = data["run_on_all_platforms"]
            run_all_updated = True

        if "target_platform_ids" in data:
            provided_ids = data["target_platform_ids"] or []
            if len(set(provided_ids)) != len(provided_ids):
                db.rollback()
                return JSONResponse({"error": "Duplicate platform IDs provided"}, status_code=400)
            new_targets = set(provided_ids)
            new_targets_set = new_targets
            if not job.run_on_all_platforms and not new_targets:
                db.rollback()
                return JSONResponse({"error": "target_platform_ids cannot be empty when run_on_all_platforms is False"}, status_code=400)

            if not job.run_on_all_platforms:
                platforms = (
                    db.query(Platform)
                    .filter(Platform.id.in_(list(new_targets)))
                    .all()
                )
                if len(platforms) != len(new_targets):
                    db.rollback()
                    return JSONResponse({"error": "One or more platform IDs are invalid"}, status_code=400)

            existing = {link.platform_id: link for link in job.platform_links}

            # Remove old links
            for platform_id, link in list(existing.items()):
                if platform_id not in new_targets:
                    db.delete(link)

            # Add new ones
            for platform_id in new_targets:
                if platform_id not in existing:
                    db.add(
                        AutomationJobPlatform(
                            id=uuid.uuid4(),
                            job_id=job.id,
                            platform_id=platform_id,
                        )
                    )

        if job.run_on_all_platforms and job.platform_links:
            for link in list(job.platform_links):
                db.delete(link)

        if run_all_updated and not job.run_on_all_platforms:
            effective_targets = new_targets_set if new_targets_set is not None else {link.platform_id for link in job.platform_links}
            if not effective_targets:
                db.rollback()
                return JSONResponse({"error": "Provide at least one target platform when disabling run_on_all_platforms"}, status_code=400)

        db.commit()
        db.refresh(job)

        log_audit(
            db,
            user=user.username if user else "system",
            action="update",
            object_type="automation_job",
            object_id=str(job.id),
            meta={"name": job.name, "trigger_type": job.trigger_type},
        )

        return JSONResponse(_build_response(job))
    except Exception as exc:  # pragma: no cover - consistency with other endpoints
        db.rollback()
        return JSONResponse({"error": str(exc)}, status_code=400)
    finally:
        db.close()


@require_roles(UserRole.ADMIN)
async def delete_job(request: Request) -> JSONResponse:
    """Delete an automation job."""

    job_id = request.path_params["job_id"]
    db: Session = _get_db_session()
    try:
        job = db.query(AutomationJob).filter(AutomationJob.id == job_id).first()
        if not job:
            return JSONResponse({"error": "Automation job not found"}, status_code=404)

        user = get_request_user(request)

        log_audit(
            db,
            user=user.username if user else "system",
            action="delete",
            object_type="automation_job",
            object_id=str(job.id),
            meta={"name": job.name},
        )

        db.delete(job)
        db.commit()

        return JSONResponse(MessageResponse(message="Automation job deleted").model_dump())
    finally:
        db.close()


@require_roles(UserRole.ADMIN, UserRole.OPERATOR)
async def run_job(request: Request) -> JSONResponse:
    """Manually trigger an automation job on all its target platforms."""

    job_id = request.path_params["job_id"]
    db: Session = _get_db_session()
    try:
        job = db.query(AutomationJob).filter(AutomationJob.id == job_id).first()
        if not job:
            return JSONResponse({"error": "Automation job not found"}, status_code=404)
        if not job.is_enabled:
            return JSONResponse({"error": "Automation job is disabled"}, status_code=400)
    finally:
        db.close()

    try:
        from app.scheduler import dispatch_automation_job
        enqueued = await dispatch_automation_job(job_id, triggered_by="manual")
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)

    user = get_request_user(request)
    db = _get_db_session()
    try:
        log_audit(
            db,
            user=user.username if user else "system",
            action="run",
            object_type="automation_job",
            object_id=str(job_id),
            meta={"triggered_by": "manual", "enqueued": len(enqueued)},
        )
    finally:
        db.close()

    return JSONResponse({
        "message": f"Dispatched {len(enqueued)} task(s)",
        "enqueued_jobs": enqueued,
    })


async def webhook_trigger(request: Request) -> JSONResponse:
    """
    Trigger an automation job via webhook.

    URL: POST /api/automations/webhook/{job_id}
    Auth: X-Hub-Signature-256 header (HMAC-SHA256 of body with job's webhook_secret)
          OR Authorization: Bearer <webhook_secret> for simple token auth.
    """

    job_id = request.path_params["job_id"]
    db: Session = _get_db_session()
    try:
        job = db.query(AutomationJob).filter(AutomationJob.id == job_id).first()
        if not job:
            return JSONResponse({"error": "Automation job not found"}, status_code=404)
        if not job.is_enabled:
            return JSONResponse({"error": "Automation job is disabled"}, status_code=400)
        if job.trigger_type not in (AutomationTriggerEnum.WEBHOOK, AutomationTriggerEnum.GITHUB_PUSH, "webhook", "github_push"):
            return JSONResponse({"error": "Job is not configured for webhook triggering"}, status_code=400)

        webhook_secret = job.webhook_secret
    finally:
        db.close()

    # Verify secret
    body = await request.body()
    if webhook_secret:
        # GitHub-style HMAC-SHA256 signature
        sig_header = request.headers.get("X-Hub-Signature-256", "")
        if sig_header.startswith("sha256="):
            expected = "sha256=" + hmac.new(
                webhook_secret.encode(), body, hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(sig_header, expected):
                return JSONResponse({"error": "Invalid signature"}, status_code=401)
        else:
            # Simple bearer token fallback
            auth = request.headers.get("Authorization", "")
            token = auth.removeprefix("Bearer ").strip()
            if not hmac.compare_digest(token, webhook_secret):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)

    try:
        from app.scheduler import dispatch_automation_job
        enqueued = await dispatch_automation_job(job_id, triggered_by="webhook")
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)

    return JSONResponse({
        "message": f"Webhook accepted, dispatched {len(enqueued)} task(s)",
        "enqueued_jobs": enqueued,
    })


routes = [
    Route("/", list_jobs, methods=["GET"]),
    Route("/", create_job, methods=["POST"]),
    Route("/webhook/{job_id:uuid}", webhook_trigger, methods=["POST"]),
    Route("/{job_id:uuid}", get_job, methods=["GET"]),
    Route("/{job_id:uuid}", update_job, methods=["PUT"]),
    Route("/{job_id:uuid}", delete_job, methods=["DELETE"]),
    Route("/{job_id:uuid}/run", run_job, methods=["POST"]),
]

automations_router = Router(routes=routes)
