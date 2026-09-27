# CareOps

A hospital knowledge assistant built for the **RxGPT Agentic AI Healthcare Platform** case study.

CareOps lets hospital staff ask natural-language questions and get answers grounded _only_
in their own hospital's approved documents — with strict tenant isolation between
hospitals, source citations on every answer, and a full audit trail.

> Note: "RxGPT" is the case-study assignment's name. The actual product built is called
> **CareOps** — that's the name shown throughout the UI.

---

## Tech Stack

| Layer            | Choice                                                |
| ---------------- | ----------------------------------------------------- |
| Frontend         | Next.js (App Router) + shadcn/ui + Tailwind           |
| Auth             | Supabase Auth — Google OAuth only                     |
| Database         | Supabase Postgres + `pgvector`                        |
| Backend          | FastAPI (Python), SQLAlchemy (raw SQL, no ORM models) |
| LLM (generation) | Google Gemini — `gemini-3.8-flash`                    |
| LLM (embeddings) | Google Gemini — `gemini-embedding-001` (768 dims)     |
| Testing          | pytest (19 tests)                                     |

**Why this stack:** Supabase was chosen so auth and the vector store share one database —
tenant-isolation filtering (`hospital_id` + `status='approved'`) happens as a single SQL
query via a Postgres function (`match_chunks`), rather than requiring a separate vector DB
and a second round-trip. Gemini was chosen for its free tier, keeping embeddings and
generation on one API key/quota family.

---

## Architecture

```
User (Google login)
      |
      v
Next.js frontend  --(JWT)-->  FastAPI backend
                                    |
                    +---------------+----------------+
                    |               |                |
              Supabase Auth   Supabase Postgres   Gemini API
              (JWKS verify)   (+pgvector)          (embed + generate)
```

### Request flow for `POST /ask`

1. JWT is verified against Supabase's JWKS endpoint (not a shared secret — this
   Supabase project uses asymmetric ES256 signing keys).
2. `hospital_id` and `role` are looked up from the `users` table using the verified
   token's subject — **never taken from the request body**. This is the core tenant-isolation
   enforcement point on the application side.
3. The question is embedded (Gemini, `retrieval_query` task type).
4. `match_chunks()` (a Postgres function) does vector similarity search **and**
   `hospital_id` + `status='approved'` filtering in one query — the enforcement point on
   the database side.
5. If no chunk clears the similarity threshold, the LLM is skipped entirely and an
   "insufficient evidence" response is returned — this avoids both hallucination and
   unnecessary LLM cost.
6. Otherwise, Gemini generates a grounded answer from the retrieved chunks, returning
   strict JSON (`answer`, `used_chunk_ids`). A malformed/empty model response is treated
   as the same "insufficient evidence" path rather than surfacing a broken answer.
7. The conversation, message, retrieval log, and audit log are all persisted.

### Document pipeline (`POST /documents` → `/process` → `/status`)

Upload → plain-text extraction → fixed-size chunking (~300 words) → embedding
(`retrieval_document` task type) → chunks stored with `status='approved'` mirroring the
parent document → admin approval flips both the document and its chunks together, so a
document can be uploaded and processed without being immediately live in chat.

Duplicate uploads (same `hospital_id` + content hash) return the existing document
instead of creating a second copy.

---

## Database Schema

Tables: `hospitals`, `users`, `documents`, `chunks`, `conversations`, `messages`,
`retrieval_logs`, `audit_logs`.

Key design choices:

- `chunks.hospital_id` is denormalized (duplicated from `documents.hospital_id`) so the
  tenant filter is a single indexed column check, not a join, on the hot retrieval path.
- `match_chunks(query_embedding, match_hospital_id, match_count)` is a `stable` SQL
  function — it's the single place tenant isolation is enforced at the data layer.
- A Postgres trigger auto-creates a `users` row (`role='pending'`, `hospital_id=NULL`) on
  first Google login; an admin manually assigns `hospital_id`/`role` afterward. There's no
  self-service hospital signup — this is intentional, since hospital assignment is an
  administrative act, not something a new user should be able to set for themselves.

---

## Setup

### Prerequisites

- Node.js, Python 3.12+, a Supabase project, a Gemini API key

### 1. Database

Run `supabase/schema.sql` in the Supabase SQL Editor. This creates all tables, the
`pgvector` extension, the `match_chunks` function, and the auto-provisioning trigger.

### 2. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

Create `.env`:

```
SUPABASE_URL=https://<project-ref>.supabase.co
DATABASE_URL=postgresql+psycopg2://<connection-string-from-supabase>
GEMINI_API_KEY=<your-key>
```

```bash
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
```

Create `.env.local`:

```
NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon-key>
```

```bash
npm run dev
```

### 4. Seed data

```bash
cd backend
python ../supabase/seed_data.py
```

Populates the 4 sample documents from the case-study brief (2 approved for Hospital A,
1 approved for Hospital B, 1 archived for Hospital A).

### 5. First-login setup

Log in once via Google with each account you want to test. This auto-creates a `users`
row with `role='pending'`. Then, in Supabase SQL Editor, assign each account a hospital
and role:

```sql
update users set hospital_id = '<hospital-id>', role = 'admin'
  where email = 'your-account@example.com';
```

---

## API Endpoints

| Method | Path                      | Auth       | Purpose                                                     |
| ------ | ------------------------- | ---------- | ----------------------------------------------------------- |
| POST   | `/ask`                    | any user   | RAG question-answering                                      |
| GET    | `/conversations`          | any user   | List own conversation history                               |
| GET    | `/conversations/{id}`     | owner only | Load a conversation's messages                              |
| POST   | `/documents`              | admin      | Upload a document (text or `.txt`)                          |
| POST   | `/documents/{id}/process` | admin      | Chunk + embed a document                                    |
| PATCH  | `/documents/{id}/status`  | admin      | Approve / archive a document                                |
| GET    | `/documents`              | any user   | List documents (staff see approved-only)                    |
| GET    | `/documents/{id}`         | any user   | Document detail (same permission split)                     |
| GET    | `/me`                     | any user   | Debug/verification endpoint — returns the caller's identity |

---

## Testing

19 pytest tests covering the scenarios this project is graded on:

- **Tenant isolation** (5 tests) — cross-hospital leakage, spoofed `hospital_id` in the
  request body, archived-document exclusion, direct document access across hospitals
- **Guardrails** (3 tests) — insufficient-evidence responses, both when no chunks are
  found and when the LLM itself signals low confidence
- **RBAC** (5 tests) — admin-only endpoints correctly reject staff, staff see
  approved-only documents
- **Document lifecycle** (4 tests) — upload → process → approve sequencing, duplicate
  upload idempotency
- **Audit logging** (2 tests) — every `/ask` call produces a corresponding audit entry
  with the correct actor

```bash
cd backend
pytest -v
```

Tests run against the real Supabase database (in isolated, self-cleaning test
hospitals/users — never touching real seeded data) but **mock all Gemini calls** with a
fixed embedding vector and a deterministic fake answer function. This keeps the suite
fast, free, and independent of external API quota/availability, while still exercising
every real SQL query and permission check.

---

## Scope: What's Real, Mocked, or Not Built

**Fully real and tested:**

- Auth, tenant isolation, RBAC
- RAG retrieval + grounded generation + citation, via real pgvector search and real
  Gemini calls (in the app itself — only the _test suite_ mocks these)
- Document upload/processing/approval pipeline
- Audit logging
- Conversation history/persistence

**Intentionally simplified:**

- **Text extraction**: plain text only (paste or `.txt` upload). No PDF parsing. A real
  hospital's documents would arrive as PDFs/Word docs; this was cut to keep the 1-day
  build focused on the harder problem (retrieval correctness, isolation), not document
  parsing.
- **Document approval**: a single admin-toggled status change, not a multi-step review
  workflow with reviewer assignment, comments, or versioned diffs.
- **Chunking**: naive fixed-size word chunking (~300 words), not semantic/sentence-aware
  chunking.
- **Similarity threshold**: currently `0.3`, tuned empirically against this project's
  short seed sentences. This is loose enough to occasionally surface a tangentially
  related chunk (e.g. a question about refunds pulling in an authorization-related chunk
  because both mention "billing") — a production system would need a larger, more
  realistic document set to tune this properly, and would likely re-rank retrieved
  chunks with a cross-encoder rather than relying on threshold-only filtering.

**Not built (by design — reasoning below instead):**

- A dedicated tool-calling agent. The brief's "agentic" framing suggests a router that
  chooses between RAG and external tool calls (e.g. a mock `get_hospital_policy()`
  lookup); this build implements pure RAG only. Given the time budget, the priority was
  making retrieval, isolation, and grounding fully correct and tested rather than adding
  a second code path that would have received comparatively less testing.
- Deployment. The app runs locally; no production hosting was set up in the available
  time.

---

## Production Thinking

The sections below describe how this system would need to change to run in production —
these are deliberately _not_ built, since they require infrastructure and operational
decisions beyond a 1-day scope.

### Scaling beyond a handful of hospitals

The current design already scales reasonably far without structural change: `chunks` is
indexed on `(hospital_id, status)` and uses an IVFFlat vector index, so query cost grows
with the _size of one hospital's_ document set, not the total across all hospitals. The
first real bottleneck would be the IVFFlat index's recall/speed tradeoff at high chunk
counts (hundreds of thousands+) — at that point, tuning the `lists` parameter or moving
to an HNSW index (pgvector supports this) would be the next step, before considering a
dedicated vector database.

### Deployment

Frontend to Vercel (straightforward, matches the Next.js app as built). Backend to a
container-based host (Render, Railway, or Fly.io) rather than a serverless function,
since FastAPI's DB connection pooling behaves better with long-lived processes. The
Supabase project itself would move from the free tier to a paid tier with connection
pooling (pgBouncer) enabled once concurrent user counts rise, since the current setup
uses Supabase's pooler connection string but hasn't been load-tested against it.

### Backup / migration

Supabase provides automatic daily backups on paid tiers; for this project's schema, the
higher-risk migration concern isn't data loss but **embedding model changes** — if the
embedding model were ever swapped (e.g. moving off `gemini-embedding-001`), every
existing chunk's embedding would need to be regenerated, since embeddings from different
models aren't comparable via cosine similarity. A production version of this system
would store the embedding model name/version alongside each chunk, so a migration could
run incrementally and be verified chunk-by-chunk rather than requiring a hard cutover.

### Observability

Currently, failures are logged via `print()` statements visible only in the local
terminal. Production would need: structured logging (e.g. JSON logs to a log aggregator),
an error-tracking service (Sentry or similar) specifically around the Gemini API calls
(since those are the most likely external failure point — as seen repeatedly during this
build, model names and availability change without notice), and a dashboard tracking
the insufficient-evidence rate over time as a proxy for whether the knowledge base is
actually covering what staff are asking.

### Content safety / compliance

Since this handles hospital policy content, a production version would add: rate
limiting per user (to prevent scraping the knowledge base via repeated questions),
stricter audit log retention policies aligned with the hospital's actual compliance
requirements (this build's `audit_logs` table has no retention/archival policy), and a
review step before any document reaches `approved` status that involves a second
approver, not just the uploader.

---

## Known Limitations

- Gemini model names have changed multiple times during this build's development window
  (both the embedding and generation models used here were mid-deprecation at time of
  writing) — model availability should be re-verified before any demo or submission.
- The similarity threshold (`0.3`) was tuned against very short seed sentences and may
  need adjustment for longer, more realistic documents.
- No PDF/Word document support — plain text only.
