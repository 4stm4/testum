# SPDX-License-Identifier: MIT
"""Audit log API endpoints."""
from datetime import datetime, timedelta

from sqlalchemy import desc
from sqlalchemy.orm import Session
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.db import get_db
from app.models import AuditLog, UserRole
from app.pagination import get_pagination_params
from app.rbac import require_roles

ALL_ROLES = [UserRole.ADMIN, UserRole.OPERATOR, UserRole.VIEWER]


@require_roles(UserRole.ADMIN, UserRole.OPERATOR)
async def list_audit_logs(request: Request):
    """List audit logs with pagination and filtering."""
    db: Session = next(get_db())
    try:
        try:
            limit, offset = get_pagination_params(request, default_limit=100, max_limit=500)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

        # Filters
        user_filter = request.query_params.get("user")
        action_filter = request.query_params.get("action")
        resource_type_filter = request.query_params.get("resource_type")
        days = request.query_params.get("days", "30")  # Default last 30 days

        try:
            days_int = int(days)
            if days_int < 1 or days_int > 365:
                days_int = 30
        except (ValueError, TypeError):
            days_int = 30

        since_date = datetime.utcnow() - timedelta(days=days_int)

        # Build query
        query = db.query(AuditLog).filter(AuditLog.timestamp >= since_date)

        if user_filter:
            query = query.filter(AuditLog.user.ilike(f"%{user_filter}%"))
        
        if action_filter:
            query = query.filter(AuditLog.action.ilike(f"%{action_filter}%"))
        
        if resource_type_filter:
            query = query.filter(AuditLog.resource_type.ilike(f"%{resource_type_filter}%"))

        total = query.count()
        logs = query.order_by(desc(AuditLog.timestamp)).offset(offset).limit(limit).all()

        items = []
        for log in logs:
            items.append({
                "id": str(log.id),
                "user": log.user,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "details": log.details,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            })

        response = JSONResponse(items)
        response.headers["X-Total-Count"] = str(total)
        response.headers["X-Limit"] = str(limit)
        response.headers["X-Offset"] = str(offset)
        return response
    finally:
        db.close()


@require_roles(UserRole.ADMIN, UserRole.OPERATOR)
async def get_audit_stats(request: Request):
    """Get audit statistics."""
    db: Session = next(get_db())
    try:
        days = int(request.query_params.get("days", "7"))
        if days < 1 or days > 365:
            days = 7
        
        since_date = datetime.utcnow() - timedelta(days=days)
        
        # Total actions
        total = db.query(AuditLog).filter(AuditLog.timestamp >= since_date).count()
        
        # Actions by type
        actions_query = db.query(
            AuditLog.action,
            db.func.count(AuditLog.id).label('count')
        ).filter(
            AuditLog.timestamp >= since_date
        ).group_by(AuditLog.action).all()
        
        actions_by_type = {action: count for action, count in actions_query}
        
        # Top users
        users_query = db.query(
            AuditLog.user,
            db.func.count(AuditLog.id).label('count')
        ).filter(
            AuditLog.timestamp >= since_date
        ).group_by(AuditLog.user).order_by(desc('count')).limit(10).all()
        
        top_users = [{"user": user, "count": count} for user, count in users_query]
        
        return JSONResponse({
            "total_actions": total,
            "actions_by_type": actions_by_type,
            "top_users": top_users,
            "period_days": days,
        })
    finally:
        db.close()


# Router
audit_router = Starlette(
    routes=[
        Route("/", list_audit_logs, methods=["GET"]),
        Route("/stats", get_audit_stats, methods=["GET"]),
    ]
)
