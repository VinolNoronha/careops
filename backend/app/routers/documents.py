"""
app/routers/documents.py

POST /documents              -- admin uploads a doc (title, department, doc_type, text)
POST /documents/{id}/process -- extraction (already-plain-text here) -> chunking ->
                                 embedding -> stores chunks, flips status to 'ready'
GET  /documents               -- list docs for the CALLER'S hospital (never client-supplied)
GET  /documents/{id}          -- single doc detail, same-hospital only

Extraction is intentionally simple for this build: plain text only (paste or
.txt upload), per the project's scope notes. No PDF parsing.
"""

import hashlib
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, Form, File
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, require_admin
from app.db.session import get_db
from app.services.chunking import chunk_text
from app.services.embeddings import embed_document
from app.services.audit import write_audit_log

router = APIRouter()


class DocumentOut(BaseModel):
    id: str
    title: str
    department: str | None
    doc_type: str | None
    version: int
    status: str
    created_at: str


class UploadResponse(BaseModel):
    id: str
    status: str


class ProcessResponse(BaseModel):
    id: str
    status: str
    chunks_created: int



@router.post("/documents", response_model=UploadResponse)
def upload_document(
    title: str = Form(...),
    department: str = Form(...),
    doc_type: str = Form(...),
    raw_text: str | None = Form(None),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    if not raw_text and not file:
        raise HTTPException(status_code=400, detail="Provide either raw_text or a file")

    if file:
        content_bytes = file.file.read()
        try:
            text_content = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=400,
                detail="Only plain text (.txt / UTF-8) files are supported in this build",
            )
    else:
        text_content = raw_text

    content_hash = hashlib.sha256(text_content.encode("utf-8")).hexdigest()

    # Idempotency check: same hospital + same content -> don't create a duplicate
    existing = db.execute(
        text(
            """
            select id, status from documents
            where hospital_id = :hospital_id and content_hash = :hash
            """
        ),
        {"hospital_id": user["hospital_id"], "hash": content_hash},
    ).fetchone()

    if existing:
        return UploadResponse(id=str(existing.id), status=existing.status)

    document_id = str(uuid.uuid4())
    db.execute(
        text(
            """
            insert into documents
                (id, hospital_id, title, department, doc_type, status,
                 content_hash, uploaded_by, raw_text)
            values
                (:id, :hospital_id, :title, :department, :doc_type, 'processing',
                 :content_hash, :uploaded_by, :raw_text)
            """
        ),
        {
            "id": document_id,
            "hospital_id": user["hospital_id"],
            "title": title,
            "department": department,
            "doc_type": doc_type,
            "content_hash": content_hash,
            "uploaded_by": user["id"],
            "raw_text": text_content,
        },
    )
    write_audit_log(db, user["id"], user["hospital_id"], "document_upload", {
        "document_id": document_id,
        "title": title,
    })
    db.commit()

    return UploadResponse(id=document_id, status="processing")


@router.post("/documents/{document_id}/process", response_model=ProcessResponse)
def process_document(
    document_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    doc = db.execute(
        text(
            """
            select id, hospital_id, raw_text, status from documents
            where id = :id
            """
        ),
        {"id": document_id},
    ).fetchone()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if str(doc.hospital_id) != str(user["hospital_id"]):
        raise HTTPException(status_code=403, detail="Document belongs to another hospital")

    if doc.status not in ("processing", "processing_failed"):
        raise HTTPException(
            status_code=400,
            detail=f"Document is already '{doc.status}', nothing to process",
        )

    try:
        chunks = chunk_text(doc.raw_text)
        if not chunks:
            raise ValueError("Document has no extractable text")

        for idx, chunk in enumerate(chunks):
            embedding = embed_document(chunk)
            embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

            db.execute(
                text(
                    """
                    insert into chunks
                        (id, document_id, hospital_id, status, chunk_index, text, embedding)
                    values
                        (:id, :document_id, :hospital_id, 'approved', :idx, :text, (:embedding)::vector)
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "document_id": document_id,
                    "hospital_id": doc.hospital_id,
                    "idx": idx,
                    "text": chunk,
                    "embedding": embedding_str,
                },
            )

        db.execute(
            text("update documents set status = 'ready', updated_at = now() where id = :id"),
            {"id": document_id},
        )
        write_audit_log(db, user["id"], user["hospital_id"], "document_processed", {
            "document_id": document_id,
            "chunks_created": len(chunks),
        })
        db.commit()

        return ProcessResponse(id=document_id, status="ready", chunks_created=len(chunks))

    except Exception as e:
        db.rollback()
        db.execute(
            text("update documents set status = 'processing_failed', updated_at = now() where id = :id"),
            {"id": document_id},
        )
        write_audit_log(db, user["id"], user["hospital_id"], "document_processing_failed", {
            "document_id": document_id,
            "error": str(e),
        })
        db.commit()
        print("Document processing failed:", repr(e))
        raise HTTPException(status_code=500, detail="Document processing failed")


class StatusUpdateRequest(BaseModel):
    status: str  # 'approved' | 'archived'


# ---------------------------------------------------------------
# PATCH /documents/{id}/status  (admin only)
# Simple approve/archive toggle — a real workflow engine is out of scope
# for this build; this satisfies the "approval flow" requirement minimally.
# Flips both the document's status AND its chunks' status together, so
# retrieval (which filters chunks on status='approved') stays consistent.
# ---------------------------------------------------------------
@router.patch("/documents/{document_id}/status", response_model=DocumentOut)
def update_document_status(
    document_id: str,
    body: StatusUpdateRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(require_admin),
):
    if body.status not in ("approved", "archived"):
        raise HTTPException(status_code=400, detail="status must be 'approved' or 'archived'")

    row = db.execute(
        text("select id, hospital_id, status from documents where id = :id"),
        {"id": document_id},
    ).fetchone()

    if not row or str(row.hospital_id) != str(user["hospital_id"]):
        raise HTTPException(status_code=404, detail="Document not found")

    if row.status not in ("ready", "approved", "archived"):
        raise HTTPException(
            status_code=400,
            detail=f"Document must be processed (status='ready') before it can be {body.status}",
        )

    db.execute(
        text("update documents set status = :status, updated_at = now() where id = :id"),
        {"status": body.status, "id": document_id},
    )
    db.execute(
        text("update chunks set status = :status where document_id = :id"),
        {"status": body.status, "id": document_id},
    )
    write_audit_log(db, user["id"], user["hospital_id"], "document_status_changed", {
        "document_id": document_id,
        "previous_status": row.status,
        "new_status": body.status,
    })
    db.commit()

    updated = db.execute(
        text(
            """
            select id, title, department, doc_type, version, status, created_at
            from documents where id = :id
            """
        ),
        {"id": document_id},
    ).fetchone()

    return DocumentOut(
        id=str(updated.id),
        title=updated.title,
        department=updated.department,
        doc_type=updated.doc_type,
        version=updated.version,
        status=updated.status,
        created_at=updated.created_at.isoformat(),
    )


# ---------------------------------------------------------------
# GET /documents  (any authenticated user, same hospital only)
# Staff see approved docs only; admins see everything for their hospital.
# ---------------------------------------------------------------
@router.get("/documents", response_model=list[DocumentOut])
def list_documents(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if user["role"] == "admin":
        rows = db.execute(
            text(
                """
                select id, title, department, doc_type, version, status, created_at
                from documents where hospital_id = :hospital_id
                order by created_at desc
                """
            ),
            {"hospital_id": user["hospital_id"]},
        ).fetchall()
    else:
        rows = db.execute(
            text(
                """
                select id, title, department, doc_type, version, status, created_at
                from documents
                where hospital_id = :hospital_id and status = 'approved'
                order by created_at desc
                """
            ),
            {"hospital_id": user["hospital_id"]},
        ).fetchall()

    return [
        DocumentOut(
            id=str(r.id),
            title=r.title,
            department=r.department,
            doc_type=r.doc_type,
            version=r.version,
            status=r.status,
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]


# ---------------------------------------------------------------
# GET /documents/{id}  (same hospital only; staff limited to approved)
# ---------------------------------------------------------------
@router.get("/documents/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    row = db.execute(
        text(
            """
            select id, hospital_id, title, department, doc_type, version, status, created_at
            from documents where id = :id
            """
        ),
        {"id": document_id},
    ).fetchone()

    if not row or str(row.hospital_id) != str(user["hospital_id"]):
        raise HTTPException(status_code=404, detail="Document not found")

    if user["role"] != "admin" and row.status != "approved":
        raise HTTPException(status_code=403, detail="Document not available")

    return DocumentOut(
        id=str(row.id),
        title=row.title,
        department=row.department,
        doc_type=row.doc_type,
        version=row.version,
        status=row.status,
        created_at=row.created_at.isoformat(),
    )

