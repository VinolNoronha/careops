"""
app/routers/audit.py

GET /audit       -- list recent audit events for the admin's own hospital
GET /audit/{id}  -- single audit event detail, same-hospital only

Read-only. audit_logs rows are written elsewhere (ask.py, documents.py) --
this router only surfaces them.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.dependencies import require_admin
from app.db.session import get_db

router = APIRouter()


class AuditLogOut(BaseModel):
    id: str
    event_type: str
    actor_email: str | None
    metadata: dict
    created_at: str


@router.get("/audit", response_model=list[AuditLogOut])
def list_audit_logs(
    limit: int = 100,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    rows = db.execute(
        text(
            """
            select a.id, a.event_type, a.metadata, a.created_at, u.email as actor_email
            from audit_logs a
            left join users u on u.id = a.actor_id
            where a.hospital_id = :hospital_id
            order by a.created_at desc
            limit :limit
            """
        ),
        {"hospital_id": user["hospital_id"], "limit": limit},
    ).fetchall()

    return [
        AuditLogOut(
            id=str(r.id),
            event_type=r.event_type,
            actor_email=r.actor_email,
            metadata=r.metadata or {},
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]


@router.get("/audit/{audit_id}", response_model=AuditLogOut)
def get_audit_log(
    audit_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    row = db.execute(
        text(
            """
            select a.id, a.event_type, a.metadata, a.created_at, a.hospital_id, u.email as actor_email
            from audit_logs a
            left join users u on u.id = a.actor_id
            where a.id = :id
            """
        ),
        {"id": audit_id},
    ).fetchone()

    if not row or str(row.hospital_id) != str(user["hospital_id"]):
        raise HTTPException(status_code=404, detail="Audit log not found")

    return AuditLogOut(
        id=str(row.id),
        event_type=row.event_type,
        actor_email=row.actor_email,
        metadata=row.metadata or {},
        created_at=row.created_at.isoformat(),
    )