"""
backend/tests/test_rbac.py

Tests that admin-only endpoints actually reject staff users, and that
staff/admin see appropriately different data.
"""

from tests.conftest import make_user


def test_staff_cannot_upload_document(client, as_user, test_data):
    as_user(make_user(test_data["staff_a"], test_data["hospital_a"], "staff"))

    res = client.post(
        "/documents",
        data={"title": "Should Fail", "department": "Test", "doc_type": "Policy", "raw_text": "x"},
    )
    assert res.status_code == 403


def test_admin_can_upload_document(client, as_user, test_data):
    as_user(make_user(test_data["admin_a"], test_data["hospital_a"], "admin"))

    res = client.post(
        "/documents",
        data={"title": "Should Succeed", "department": "Test", "doc_type": "Policy", "raw_text": "x"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "processing"


def test_staff_cannot_change_document_status(client, as_user, test_data):
    as_user(make_user(test_data["staff_a"], test_data["hospital_a"], "staff"))

    res = client.patch(
        f"/documents/{test_data['doc_approved_a']}/status",
        json={"status": "archived"},
    )
    assert res.status_code == 403


def test_staff_only_sees_approved_documents(client, as_user, test_data):
    as_user(make_user(test_data["staff_a"], test_data["hospital_a"], "staff"))

    res = client.get("/documents")
    titles = [d["title"] for d in res.json()]

    assert "TEST Approved Doc A" in titles
    assert "TEST Archived Doc A" not in titles


def test_admin_sees_all_statuses(client, as_user, test_data):
    as_user(make_user(test_data["admin_a"], test_data["hospital_a"], "admin"))

    res = client.get("/documents")
    titles = [d["title"] for d in res.json()]

    assert "TEST Approved Doc A" in titles
    assert "TEST Archived Doc A" in titles