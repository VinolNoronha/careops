"""
Conversation history endpoints.

GET /conversations
    Returns the authenticated user's conversations.

GET /conversations/{conversation_id}
    Returns one conversation and its messages.

All queries are scoped to the authenticated user's
user_id AND hospital_id.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.dependencies import get_current_user
from app.db.session import get_db


router = APIRouter(
    prefix="/conversations",
    tags=["Conversations"],
)

class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: str


class ConversationMessage(BaseModel):
    id: str
    role: str
    content: str
    sources: list = []
    insufficient_evidence: bool = False
    created_at: str


class ConversationDetail(BaseModel):
    id: str
    title: str
    created_at: str
    messages: list[ConversationMessage]




@router.get("", response_model=list[ConversationSummary])
def list_conversations(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = user["id"]
    hospital_id = user["hospital_id"]

    rows = db.execute(
        text(
            """
            SELECT id, title, created_at
            FROM conversations
            WHERE user_id = :user_id
              AND hospital_id = :hospital_id
            ORDER BY created_at DESC
            """
        ),
        {
            "user_id": user_id,
            "hospital_id": hospital_id,
        },
    ).fetchall()

    return [
        ConversationSummary(
            id=str(row.id),
            title=row.title or "New conversation",
            created_at=str(row.created_at),
        )
        for row in rows
    ]


@router.get(
    "/{conversation_id}",
    response_model=ConversationDetail,
)
def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = user["id"]
    hospital_id = user["hospital_id"]

   

    conversation = db.execute(
        text(
            """
            SELECT id, title, created_at
            FROM conversations
            WHERE id = :conversation_id
              AND user_id = :user_id
              AND hospital_id = :hospital_id
            """
        ),
        {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "hospital_id": hospital_id,
        },
    ).fetchone()

    if not conversation:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        )


    rows = db.execute(
        text(
            """
            SELECT
                id,
                role,
                question,
                answer,
                sources,
                insufficient_evidence,
                created_at
            FROM messages
            WHERE conversation_id = :conversation_id
            ORDER BY created_at ASC
            """
        ),
        {
            "conversation_id": conversation_id,
        },
    ).fetchall()

    messages = []

    for row in rows:
        if row.role == "user":
            content = row.question or ""
        else:
            content = row.answer or ""

        messages.append(
            ConversationMessage(
                id=str(row.id),
                role=row.role,
                content=content,
                sources=row.sources or [],
                insufficient_evidence=bool(
                    row.insufficient_evidence
                ),
                created_at=str(row.created_at),
            )
        )

    return ConversationDetail(
        id=str(conversation.id),
        title=conversation.title or "New conversation",
        created_at=str(conversation.created_at),
        messages=messages,
    )