"""
app/routers/ask.py

POST /ask — the core RAG endpoint.

Flow:
  1. Auth (hospital_id/role come from get_current_user, never from the client)
  2. Load/create conversation
  3. Embed the question
  4. Retrieve chunks (tenant-isolated, status='approved' enforced in SQL)
  5. Guardrail: if no strong matches, skip the LLM call entirely and
     return an insufficient-evidence response
  6. Generate a grounded answer via Gemini
  7. Persist message, retrieval_log rows, audit_log row
  8. Return answer + sources to the frontend
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.dependencies import get_current_user
from app.db.session import get_db
from app.services.embeddings import embed_query
from app.services.retrieval import retrieve_chunks
from app.services.llm import generate_answer

router = APIRouter()

CONVERSATION_HISTORY_TURNS = 6  # last N messages to include as context


class AskRequest(BaseModel):
    question: str
    conversation_id: str | None = None

class SourceOut(BaseModel):
    document_id: str
    title: str
    chunk_id: str
    snippet: str

class AskResponse(BaseModel):
    answer: str
    sources: list[SourceOut]
    insufficient_evidence: bool
    conversation_id: str



@router.post("/ask", response_model=AskResponse)
def ask(
    body: AskRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    hospital_id = user["hospital_id"]  
    user_id = user["id"]

    #Load or create conversation
    if body.conversation_id:
        convo = db.execute(
            text("select id, user_id, hospital_id from conversations where id = :id"),
            {"id": body.conversation_id},
        ).fetchone()
        if not convo or str(convo.user_id) != str(user_id):
            raise HTTPException(status_code=403, detail="Conversation not found or not yours")
        conversation_id = str(convo.id)
    else:
        conversation_id = str(uuid.uuid4())
        db.execute(
            text(
                """
                insert into conversations (id, user_id, hospital_id, title)
                values (:id, :user_id, :hospital_id, :title)
                """
            ),
            {
                "id": conversation_id,
                "user_id": user_id,
                "hospital_id": hospital_id,
                "title": body.question[:80],
            },
        )
        db.commit()

    #Load recent conversation history for context
    history_rows = db.execute(
        text(
            """
            select role, question, answer from messages
            where conversation_id = :cid
            order by created_at desc
            limit :n
            """
        ),
        {"cid": conversation_id, "n": CONVERSATION_HISTORY_TURNS},
    ).fetchall()

    conversation_history = []
    for row in reversed(history_rows):  # chronological order
        if row.role == "user":
            conversation_history.append({"role": "user", "content": row.question})
        else:
            conversation_history.append({"role": "assistant", "content": row.answer or ""})

    #Persist the user's message immediately
    user_message_id = str(uuid.uuid4())
    db.execute(
        text(
            """
            insert into messages (id, conversation_id, role, question)
            values (:id, :cid, 'user', :question)
            """
        ),
        {"id": user_message_id, "cid": conversation_id, "question": body.question},
    )
    db.commit()

    # Embed question + retrieve chunks (tenant-isolated) 
    query_embedding = embed_query(body.question)
    chunks = retrieve_chunks(db, query_embedding, hospital_id)

    # Guardrail: insufficient evidence -> skip LLM entirely 
    if not chunks:
        assistant_message_id = str(uuid.uuid4())
        db.execute(
            text(
                """
                insert into messages
                    (id, conversation_id, role, answer, sources, insufficient_evidence)
                values (:id, :cid, 'assistant', '', '[]'::jsonb, true)
                """
            ),
            {"id": assistant_message_id, "cid": conversation_id},
        )
        _write_audit_log(db, user_id, hospital_id, "ask", {
            "conversation_id": conversation_id,
            "question": body.question,
            "result": "insufficient_evidence",
        })
        db.commit()

        return AskResponse(
            answer="",
            sources=[],
            insufficient_evidence=True,
            conversation_id=conversation_id,
        )

    # Generate grounded answer 
    result = generate_answer(body.question, chunks, conversation_history)

    # LLM itself decided evidence was insufficient (empty answer, per its own instructions)
    if not result["answer"]:
        assistant_message_id = str(uuid.uuid4())
        db.execute(
            text(
                """
                insert into messages
                    (id, conversation_id, role, answer, sources, insufficient_evidence)
                values (:id, :cid, 'assistant', '', '[]'::jsonb, true)
                """
            ),
            {"id": assistant_message_id, "cid": conversation_id},
        )
        _write_audit_log(db, user_id, hospital_id, "ask", {
            "conversation_id": conversation_id,
            "question": body.question,
            "result": "llm_insufficient_evidence",
        })
        db.commit()

        return AskResponse(
            answer="",
            sources=[],
            insufficient_evidence=True,
            conversation_id=conversation_id,
        )

    # Build sources list (only chunks the LLM actually cited)
    
    chunk_lookup = {str(c["chunk_id"]): c for c in chunks}
    # print("DEBUG chunk_lookup keys:", [(k, type(k)) for k in chunk_lookup.keys()])
    # print("DEBUG used_chunk_ids from LLM:", result.get("used_chunk_ids", []))
    # used_chunk_ids = [cid for cid in result["used_chunk_ids"] if cid in chunk_lookup]
    # # Fallback: if the model didn't cite anything specific, show all retrieved chunks
    # if not used_chunk_ids:
    #     used_chunk_ids = list(chunk_lookup.keys())

    used_chunk_ids = [
        cid
        for cid in result.get("used_chunk_ids", [])
        if cid in chunk_lookup
    ]

    # sources = [
    #     SourceOut(
    #         document_id=str(chunk_lookup[cid]["document_id"]),
    #         chunk_id=str(cid),
    #         snippet=chunk_lookup[cid]["text"][:200],
    #     )
    #     for cid in used_chunk_ids
    # ]
    sources = [
        SourceOut(
            document_id=str(chunk_lookup[cid]["document_id"]),
            title=chunk_lookup[cid]["document_title"],
            chunk_id=str(cid),
            snippet=chunk_lookup[cid]["text"][:200],
        )
        for cid in used_chunk_ids
    ]

    # Persist assistant message + retrieval logs + audit log 
    assistant_message_id = str(uuid.uuid4())
    sources_json = [s.model_dump() for s in sources]

    db.execute(
        text(
            """
            insert into messages
                (id, conversation_id, role, answer, sources, insufficient_evidence)
            values (:id, :cid, 'assistant', :answer, :sources, false)
            """
        ),
        {
            "id": assistant_message_id,
            "cid": conversation_id,
            "answer": result["answer"],
            "sources": _to_jsonb(sources_json),
        },
    )

    for c in chunks:
        db.execute(
            text(
                """
                insert into retrieval_logs (id, message_id, chunk_id, similarity_score)
                values (:id, :mid, :chunk_id, :score)
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "mid": assistant_message_id,
                "chunk_id": c["chunk_id"],
                "score": c["similarity"],
            },
        )

    _write_audit_log(db, user_id, hospital_id, "ask", {
        "conversation_id": conversation_id,
        "question": body.question,
        "result": "answered",
        "chunks_used": len(used_chunk_ids),
    })

    db.commit()

    return AskResponse(
        answer=result["answer"],
        sources=sources,
        insufficient_evidence=False,
        conversation_id=conversation_id,
    )


def _write_audit_log(db: Session, actor_id: str, hospital_id: str, event_type: str, metadata: dict):
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
            "metadata": _to_jsonb(metadata),
        },
    )


def _to_jsonb(value):
    """Small helper so dicts/lists get passed as proper JSON to Postgres jsonb columns."""
    import json
    return json.dumps(value)