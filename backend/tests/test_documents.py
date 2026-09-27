"""
backend/tests/test_documents.py

Document upload/processing lifecycle, and duplicate-upload idempotency.
"""

from tests.conftest import make_user


def test_upload_creates_processing_status(client, as_user, test_data):
    as_user(make_user(test_data["admin_a"], test_data["hospital_a"], "admin"))

    res = client.post(
        "/documents",
        data={"title": "Lifecycle Test Doc", "department": "Test", "doc_type": "Policy",
              "raw_text": "This is a brand new test document for the lifecycle test."},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "processing"


def test_process_creates_chunks_and_flips_to_ready(client, as_user, test_data):
    as_user(make_user(test_data["admin_a"], test_data["hospital_a"], "admin"))

    upload_res = client.post(
        "/documents",
        data={"title": "Process Test Doc", "department": "Test", "doc_type": "Policy",
              "raw_text": "Some unique content for the process test."},
    )
    doc_id = upload_res.json()["id"]

    process_res = client.post(f"/documents/{doc_id}/process")
    body = process_res.json()

    assert process_res.status_code == 200
    assert body["status"] == "ready"
    assert body["chunks_created"] >= 1


def test_duplicate_upload_is_idempotent(client, as_user, test_data):
    """Uploading the exact same content twice should NOT create a second
    document row -- it should return the existing one."""
    as_user(make_user(test_data["admin_a"], test_data["hospital_a"], "admin"))

    payload = {
        "title": "Duplicate Test Doc",
        "department": "Test",
        "doc_type": "Policy",
        "raw_text": "This exact text will be uploaded twice on purpose.",
    }

    first = client.post("/documents", data=payload)
    second = client.post("/documents", data=payload)

    assert first.json()["id"] == second.json()["id"]


def test_document_must_be_processed_before_approval(client, as_user, test_data):
    as_user(make_user(test_data["admin_a"], test_data["hospital_a"], "admin"))

    upload_res = client.post(
        "/documents",
        data={"title": "Unprocessed Doc", "department": "Test", "doc_type": "Policy",
              "raw_text": "Not processed yet."},
    )
    doc_id = upload_res.json()["id"]

    # Still in 'processing' status -- approving now should fail
    res = client.patch(f"/documents/{doc_id}/status", json={"status": "approved"})
    assert res.status_code == 400