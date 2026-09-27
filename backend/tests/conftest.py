"""
backend/tests/conftest.py

Shared pytest fixtures for the whole test suite.

Strategy:

- Uses the REAL Supabase DB (via the app's normal DATABASE_URL) but creates
  its OWN isolated test hospitals/users/documents/chunks, all cleaned up
  after the test session. Never touches your real seeded data.

- Auth is bypassed entirely via FastAPI's dependency_overrides — no real
  JWT/Google login needed, tests just say "act as this user".

- Gemini embeddings + generation are MOCKED (fixed vector, deterministic
  fake answer) so tests are fast, free, and don't burn API quota.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.db.session import SessionLocal
from app.dependencies import get_current_user, require_admin
import app.routers.ask as ask_module
import app.routers.documents as documents_module


# A fixed 768-dim vector used everywhere instead of calling real Gemini.
# All approved test chunks are seeded with this EXACT vector, so a query
# embedded with this same vector always matches them with similarity 1.0.
# Deterministic, no external API calls needed.
FIXED_EMBEDDING = [0.1] * 768



@pytest.fixture(autouse=True)
def mock_ai_calls(monkeypatch):
    monkeypatch.setattr(
        ask_module,
        "embed_query",
        lambda text: FIXED_EMBEDDING,
    )

    monkeypatch.setattr(
        documents_module,
        "embed_document",
        lambda text: FIXED_EMBEDDING,
    )

    def fake_generate_answer(question, chunks, conversation_history):
        if not chunks:
            return {
                "answer": "",
                "used_chunk_ids": [],
            }

        return {
            "answer": f"[MOCK ANSWER] {chunks[0]['text']}",
            "used_chunk_ids": [c["chunk_id"] for c in chunks],
        }

    monkeypatch.setattr(
        ask_module,
        "generate_answer",
        fake_generate_answer,
    )



@pytest.fixture(scope="session")
def db():
    session = SessionLocal()
    yield session
    session.close()



@pytest.fixture(scope="session")
def test_data(db):
   

    hospital_a = str(uuid.uuid4())
    hospital_b = str(uuid.uuid4())
    hospital_empty = str(uuid.uuid4())

    admin_a = str(uuid.uuid4())
    staff_a = str(uuid.uuid4())
    staff_b = str(uuid.uuid4())
    staff_empty = str(uuid.uuid4())

    doc_approved_a = str(uuid.uuid4())
    doc_archived_a = str(uuid.uuid4())
    doc_approved_b = str(uuid.uuid4())

    embedding_str = "[" + ",".join(
        str(x) for x in FIXED_EMBEDDING
    ) + "]"

   
    db.execute(
        text(
            "INSERT INTO hospitals (id, name) "
            "VALUES (:id, :name)"
        ),
        [
            {
                "id": hospital_a,
                "name": "TEST Hospital A",
            },
            {
                "id": hospital_b,
                "name": "TEST Hospital B",
            },
            {
                "id": hospital_empty,
                "name": "TEST Hospital Empty",
            },
        ],
    )


    db.execute(
        text(
            "INSERT INTO users "
            "(id, email, hospital_id, role) "
            "VALUES "
            "(:id, :email, :hospital_id, :role)"
        ),
        [
            {
                "id": admin_a,
                "email": "test-admin-a@test.com",
                "hospital_id": hospital_a,
                "role": "admin",
            },
            {
                "id": staff_a,
                "email": "test-staff-a@test.com",
                "hospital_id": hospital_a,
                "role": "staff",
            },
            {
                "id": staff_b,
                "email": "test-staff-b@test.com",
                "hospital_id": hospital_b,
                "role": "staff",
            },
            {
                "id": staff_empty,
                "email": "test-staff-empty@test.com",
                "hospital_id": hospital_empty,
                "role": "staff",
            },
        ],
    )


    db.execute(
        text(
            """
            INSERT INTO documents (
                id,
                hospital_id,
                title,
                department,
                doc_type,
                status,
                raw_text
            )
            VALUES (
                :id,
                :hospital_id,
                :title,
                :dept,
                :doc_type,
                :status,
                :raw_text
            )
            """
        ),
        [
            {
                "id": doc_approved_a,
                "hospital_id": hospital_a,
                "title": "TEST Approved Doc A",
                "dept": "Test",
                "doc_type": "Policy",
                "status": "approved",
                "raw_text": "Hospital A approved content.",
            },
            {
                "id": doc_archived_a,
                "hospital_id": hospital_a,
                "title": "TEST Archived Doc A",
                "dept": "Test",
                "doc_type": "Policy",
                "status": "archived",
                "raw_text": "Hospital A archived content.",
            },
            {
                "id": doc_approved_b,
                "hospital_id": hospital_b,
                "title": "TEST Approved Doc B",
                "dept": "Test",
                "doc_type": "Policy",
                "status": "approved",
                "raw_text": "Hospital B approved content.",
            },
        ],
    )


    for doc_id, hosp_id, status, chunk_text in [
        (
            doc_approved_a,
            hospital_a,
            "approved",
            "Hospital A approved content.",
        ),
        (
            doc_archived_a,
            hospital_a,
            "archived",
            "Hospital A archived content.",
        ),
        (
            doc_approved_b,
            hospital_b,
            "approved",
            "Hospital B approved content.",
        ),
    ]:
        db.execute(
            text(
                """
                INSERT INTO chunks (
                    id,
                    document_id,
                    hospital_id,
                    status,
                    chunk_index,
                    text,
                    embedding
                )
                VALUES (
                    :id,
                    :doc_id,
                    :hosp_id,
                    :status,
                    0,
                    :text,
                    (:embedding)::vector
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "doc_id": doc_id,
                "hosp_id": hosp_id,
                "status": status,
                "text": chunk_text,
                "embedding": embedding_str,
            },
        )

    db.commit()

    

    data = {
        "hospital_a": hospital_a,
        "hospital_b": hospital_b,
        "hospital_empty": hospital_empty,

        "admin_a": admin_a,
        "staff_a": staff_a,
        "staff_b": staff_b,
        "staff_empty": staff_empty,

        "doc_approved_a": doc_approved_a,
        "doc_archived_a": doc_archived_a,
        "doc_approved_b": doc_approved_b,
    }

    yield data


    params = {
        "a": hospital_a,
        "b": hospital_b,
        "empty": hospital_empty,
    }

    # Retrieval logs
    db.execute(
        text(
            """
            DELETE FROM retrieval_logs
            WHERE message_id IN (
                SELECT id
                FROM messages
                WHERE conversation_id IN (
                    SELECT id
                    FROM conversations
                    WHERE hospital_id IN (:a, :b, :empty)
                )
            )
            """
        ),
        params,
    )

    # Messages
    db.execute(
        text(
            """
            DELETE FROM messages
            WHERE conversation_id IN (
                SELECT id
                FROM conversations
                WHERE hospital_id IN (:a, :b, :empty)
            )
            """
        ),
        params,
    )

    # Conversations
    db.execute(
        text(
            """
            DELETE FROM conversations
            WHERE hospital_id IN (:a, :b, :empty)
            """
        ),
        params,
    )

    # Audit logs
    db.execute(
        text(
            """
            DELETE FROM audit_logs
            WHERE hospital_id IN (:a, :b, :empty)
            """
        ),
        params,
    )

    # Chunks
    db.execute(
        text(
            """
            DELETE FROM chunks
            WHERE hospital_id IN (:a, :b, :empty)
            """
        ),
        params,
    )

    # Documents
    db.execute(
        text(
            """
            DELETE FROM documents
            WHERE hospital_id IN (:a, :b, :empty)
            """
        ),
        params,
    )

    # Users
    db.execute(
        text(
            """
            DELETE FROM users
            WHERE hospital_id IN (:a, :b, :empty)
            """
        ),
        params,
    )

    # Hospitals
    db.execute(
        text(
            """
            DELETE FROM hospitals
            WHERE id IN (:a, :b, :empty)
            """
        ),
        params,
    )

    db.commit()



def make_user(
    user_id: str,
    hospital_id: str,
    role: str,
    email: str = "test@test.com",
):
    return {
        "id": user_id,
        "email": email,
        "hospital_id": hospital_id,
        "role": role,
        "department": None,
    }


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def as_user():
    """
    Usage:
        as_user(user_dict)

    Overrides auth for the duration of one test and
    clears the override automatically afterward.
    """

    applied = []

    def _apply(user: dict):
        def fake_get_current_user():
            return user

        def fake_require_admin():
            if user["role"] != "admin":
                from fastapi import HTTPException

                raise HTTPException(
                    status_code=403,
                    detail="Admin access required",
                )

            return user

        app.dependency_overrides[get_current_user] = (
            fake_get_current_user
        )

        app.dependency_overrides[require_admin] = (
            fake_require_admin
        )

        applied.append(True)

    yield _apply

    app.dependency_overrides.pop(
        get_current_user,
        None,
    )

    app.dependency_overrides.pop(
        require_admin,
        None,
    )