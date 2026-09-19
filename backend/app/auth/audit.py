"""audit_log: who did what, when. Never passwords, codes, CAPTCHA answers or message text."""

import uuid

from sqlalchemy.orm import Session

from app.auth import clock
from app.db.models import AuditLog


def record(
    db: Session,
    event: str,
    outcome: str,
    *,
    user_id: str | None = None,
    client_trace_id: str | None = None,
    detail: str = "",
    ip: str | None = None,
    request_id: str | None = None,
) -> str:
    """Write one row and return its server-generated request_id (a UUID)."""
    request_id = request_id or str(uuid.uuid4())
    db.add(
        AuditLog(
            at=clock.now(), event=event, user_id=user_id, request_id=request_id,
            client_trace_id=client_trace_id, outcome=outcome, detail=detail, ip=ip,
        )
    )
    db.commit()
    return request_id
