"""
backend/tests/test_tenant_isolation.py

The single most important thing this project has to prove: a user from
one hospital can NEVER see another hospital's data, no matter how the
request is crafted.
"""

from tests.conftest import make_user


def test_hospital_a_user_gets_only_hospital_a_content(client, as_user, test_data):
    as_user(make_user(test_data["staff_a"], test_data["hospital_a"], "staff"))

    res = client.post("/ask", json={"question": "Tell me about the approved content"})
    body = res.json()

    assert res.status_code == 200
    assert body["insufficient_evidence"] is False
    document_ids = [s["document_id"] for s in body["sources"]]
    assert test_data["doc_approved_a"] in document_ids
    assert test_data["doc_approved_b"] not in document_ids


def test_hospital_b_user_gets_only_hospital_b_content(client, as_user, test_data):
    as_user(make_user(test_data["staff_b"], test_data["hospital_b"], "staff"))

    res = client.post("/ask", json={"question": "Tell me about the approved content"})
    body = res.json()

    assert res.status_code == 200
    assert body["insufficient_evidence"] is False
    document_ids = [s["document_id"] for s in body["sources"]]
    assert test_data["doc_approved_b"] in document_ids
    assert test_data["doc_approved_a"] not in document_ids


def test_archived_document_never_returned(client, as_user, test_data):
    """Hospital A has an archived doc with the SAME fixed embedding as the
    approved one -- if the archived doc leaked through, this test would
    catch it, since both chunks are equally 'similar' to the query."""
    as_user(make_user(test_data["staff_a"], test_data["hospital_a"], "staff"))

    res = client.post("/ask", json={"question": "Tell me about the content"})
    body = res.json()

    document_ids = [s["document_id"] for s in body["sources"]]
    assert test_data["doc_archived_a"] not in document_ids


def test_client_cannot_spoof_hospital_id(client, as_user, test_data):
    """hospital_id must come from the authenticated user, never the request
    body -- even if a malicious client includes one, it must be ignored."""
    as_user(make_user(test_data["staff_a"], test_data["hospital_a"], "staff"))

    res = client.post(
        "/ask",
        json={
            "question": "Tell me about the approved content",
            "hospital_id": test_data["hospital_b"],  # not a real field -- should be ignored
        },
    )
    body = res.json()

    document_ids = [s["document_id"] for s in body["sources"]]
    assert test_data["doc_approved_b"] not in document_ids
    assert test_data["doc_approved_a"] in document_ids


def test_direct_document_access_blocked_across_hospitals(client, as_user, test_data):
    """Hospital B user should not be able to fetch Hospital A's document by
    guessing/knowing its id."""
    as_user(make_user(test_data["staff_b"], test_data["hospital_b"], "staff"))

    res = client.get(f"/documents/{test_data['doc_approved_a']}")
    assert res.status_code == 404