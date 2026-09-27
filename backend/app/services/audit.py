"""
app/services/audit.py

Shared audit_logs writer, used by any router that needs to record an event.
Kept as a plain function (not a class) since it's a single insert with no state.
"""

import uuid
import json
from sqlalchemy import text
from sqlalchemy.orm import Session


def write_audit_log(
    db: Session,
    actor_id: str,
    hospital_id: str,
    event_type: str,
    metadata: dict,
):
    db.execute(
        text(
            """
            insert into audit_logs (id, actor_id, hospital_id, event_type, metadata)
            values (:id, :actor_id, :hospital_id, :event_type, :metadata)
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "actor_id": actor_id,
            "hospital_id": hospital_id,
            "event_type": event_type,
            "metadata": json.dumps(metadata),
        },
    )