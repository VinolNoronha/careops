"""
backend/tests/test_audit_logging.py

Confirms /ask calls actually produce audit trail entries.
"""

from sqlalchemy import text
from tests.conftest import make_user


def test_ask_creates_audit_log_entry(client, as_user, test_data, db):
    as_user(make_user(test_data["staff_a"], test_data["hospital_a"], "staff"))

    res = client.post("/ask", json={"question": "Tell me about the approved content"})
    conversation_id = res.json()["conversation_id"]

    row = db.execute(
        text(
            """
            select event_type, metadata from audit_logs
            where hospital_id = :hospital_id
            and metadata->>'conversation_id' = :cid
            """
        ),
        {"hospital_id": test_data["hospital_a"], "cid": conversation_id},
    ).fetchone()

    assert row is not None
    assert row.event_type == "ask"


def test_audit_log_records_correct_actor(client, as_user, test_data, db):
    as_user(make_user(test_data["staff_a"], test_data["hospital_a"], "staff"))

    res = client.post("/ask", json={"question": "Tell me about the approved content"})
    conversation_id = res.json()["conversation_id"]

    row = db.execute(
        text(
            """
            select actor_id from audit_logs
            where metadata->>'conversation_id' = :cid
            """
        ),
        {"cid": conversation_id},
    ).fetchone()

    assert str(row.actor_id) == test_data["staff_a"]