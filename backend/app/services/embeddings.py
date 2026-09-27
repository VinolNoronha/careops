"""
app/services/embeddings.py

Wraps Gemini's embedding API for use inside FastAPI request handlers.
Uses the same model as seed_data.py so query embeddings and document
embeddings live in the same vector space.
"""

import google.generativeai as genai
from app.config import settings

genai.configure(api_key=settings.gemini_api_key)

EMBEDDING_MODEL = "models/gemini-embedding-001"


def embed_query(text: str) -> list[float]:
    """
    Embed a user's question for retrieval.
    task_type='retrieval_query' is intentionally different from the
    'retrieval_document' type used when embedding documents — Gemini's
    embedding model optimizes each side of the pair differently.
    """
    result = genai.embed_content(
        model=EMBEDDING_MODEL,
        content=text,
        task_type="retrieval_query",
        output_dimensionality=768,
    )
    return result["embedding"]


def embed_document(text: str) -> list[float]:
    """
    Embed a document chunk for storage. Uses 'retrieval_document' task_type,
    matching supabase/seed_data.py's approach so uploaded documents live in
    the same vector space as seeded ones.
    """
    result = genai.embed_content(
        model=EMBEDDING_MODEL,
        content=text,
        task_type="retrieval_document",
        output_dimensionality=768,
    )
    return result["embedding"]