# SPDX-License-Identifier: MIT
"""Audit logging helper."""
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.models import AuditLog

# Configure JSON logging
logger = logging.getLogger(__name__)


def log_audit(
    db: Session,
    user: str,
    action: str,
    object_type: str,
    object_id: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    """
    Create an audit log entry.

    Args:
        db: Database session
        user: User identifier
        action: Action performed (e.g., 'create', 'delete', 'update')
        object_type: Type of object (e.g., 'ssh_key', 'platform', 'task')
        object_id: ID of the object affected
        meta: Additional metadata as dictionary

    Returns:
        Created AuditLog entry
    """
    meta_serialized = None
    if meta is not None:
        # Ensure JSON-serializable payload (UUID, datetime, etc.)
        meta_serialized = json.loads(json.dumps(meta, default=str))

    audit_entry = AuditLog(
        user=user,
        action=action,
        object_type=object_type,
        object_id=object_id,
        meta=meta_serialized,
        timestamp=datetime.utcnow(),
    )
    
    db.add(audit_entry)
    db.commit()
    db.refresh(audit_entry)

    # Log to application logs
    log_data = {
        "timestamp": audit_entry.timestamp.isoformat(),
        "user": user,
        "action": action,
        "object_type": object_type,
        "object_id": object_id,
        "meta": meta_serialized,
    }
    logger.info(f"AUDIT: {json.dumps(log_data)}")

    return audit_entry

