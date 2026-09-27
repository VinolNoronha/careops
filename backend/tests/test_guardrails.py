"""
backend/tests/test_guardrails.py

Tests the "don't hallucinate, say you don't know" requirement.
"""

from tests.conftest import make_user


def test_no_matching_evidence_returns_insufficient(client, as_user, test_data):
    as_user(
        make_user(
            test_data["staff_empty"],
            test_data["hospital_empty"],
            "staff",
        )
    )

    res = client.post("/ask", json={"question": "Anything at all"})
    body = res.json()

    assert res.status_code == 200
    assert body["insufficient_evidence"] is True
    assert body["answer"] == ""
    assert body["sources"] == []

def test_insufficient_evidence_still_creates_conversation(
    client,
    as_user,
    test_data
):
    as_user(
        make_user(
            test_data["staff_empty"],
            test_data["hospital_empty"],
            "staff",
        )
    )

    res = client.post("/ask", json={"question": "Anything at all"})
    body = res.json()

    assert body["conversation_id"] is not None
    assert len(body["conversation_id"]) > 0


def test_llm_empty_answer_also_treated_as_insufficient(client, as_user, test_data, monkeypatch):
    """If chunks ARE found but the LLM itself returns an empty answer
    (per its own instructions when context is weak), the API must still
    report insufficient_evidence=True rather than returning a blank
    'successful' answer."""
    import app.routers.ask as ask_module

    monkeypatch.setattr(
        ask_module,
        "generate_answer",
        lambda question, chunks, history: {"answer": "", "used_chunk_ids": []},
    )

    as_user(make_user(test_data["staff_a"], test_data["hospital_a"], "staff"))
    res = client.post("/ask", json={"question": "Tell me about the approved content"})
    body = res.json()

    assert body["insufficient_evidence"] is True
    assert body["answer"] == ""