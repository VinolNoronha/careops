"""
app/services/chunking.py

Naive fixed-size word chunking — same approach as supabase/seed_data.py,
factored out so both the seed script and the live upload pipeline share
identical chunking behavior.
"""

CHUNK_SIZE_WORDS = 300


def chunk_text(text: str, size: int = CHUNK_SIZE_WORDS) -> list[str]:
    words = text.split()
    if not words:
        return []
    return [
        " ".join(words[i: i + size])
        for i in range(0, len(words), size)
    ]