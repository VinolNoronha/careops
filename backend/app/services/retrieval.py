"""
app/services/retrieval.py

Calls the match_chunks() Postgres function (defined in supabase/schema.sql).
hospital_id ALWAYS comes from the authenticated user object — this function
signature makes it structurally impossible to pass a client-supplied value.
"""

from sqlalchemy import text
from sqlalchemy.orm import Session

# Below this similarity score, a chunk is considered too weak to trust.
# Cosine similarity ranges 0-1 here (1 - cosine distance); tune based on testing.
SIMILARITY_THRESHOLD = 0.55

# Max chunks to pull per question
MATCH_COUNT = 5


def retrieve_chunks(db: Session, query_embedding: list[float], hospital_id: str):
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    rows = db.execute(
        text(
            """
            select chunk_id, document_id, text, similarity
            from match_chunks(
                query_embedding => (:embedding)::vector,
                match_hospital_id => :hospital_id,
                match_count => :match_count
            )
            """
        ),
        {
            "embedding": embedding_str,
            "hospital_id": hospital_id,
            "match_count": MATCH_COUNT,
        },
    ).mappings().all()

    strong_matches = [r for r in rows if r["similarity"] >= SIMILARITY_THRESHOLD]

    if not strong_matches:
        return []

    # Fetch titles for the matched documents in one batch query.
    doc_ids = list({r["document_id"] for r in strong_matches})
    title_rows = db.execute(
        text("select id, title from documents where id = any(:ids)"),
        {"ids": doc_ids},
    ).mappings().all()
    title_lookup = {row["id"]: row["title"] for row in title_rows}

    return [
        {**dict(r), "document_title": title_lookup.get(r["document_id"], "Untitled")}
        for r in strong_matches
    ]

