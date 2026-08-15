# SwasthiQ — EOD Billing & Analytics Agent

A clinic billing reconciliation, analytics, and AI-narrative tool, built for the SwasthiQ SDE Intern take-home assignment.

```
backend/    Python REST API (FastAPI + SQLite)
frontend/   React app (Vite)
```

## Architecture

```
Upload (JSON) -> Ingestion/Validation -> Deterministic Engine -> SQLite -> REST API -> React UI
                                              |
                                   (ground truth, NO LLM here)
                                              |
                                              v
                                     Narrative Layer (LLM)
                                   generate -> validate grounding -> retry once -> fallback template
```

Three layers, in dependency order:

1. **Deterministic layer** (`app/engine/`) — pure arithmetic over validated `Visit` objects. Never imports anything LLM-related. This is the ground truth everything else is checked against.
2. **Persistence layer** (`app/storage/`) — SQLite, raw SQL (no ORM — see "Data consistency" below).
3. **Narrative layer** (`app/narrative/`) — an LLM writes a WhatsApp-style summary of the deterministic report, but every number in that summary is checked against a whitelist built from the report itself before it's ever shown to a user. If the LLM is unavailable, its output is malformed, or it can't produce a grounded summary after one retry, a deterministic template (grounded by construction) is used instead.

## Key design decisions

These were deliberate calls, not defaults — documented here since the brief asks for the reasoning, not just the code:

- **Money is stored as integer paise throughout**, never float rupees. Floats introduce rounding drift that would break exact-number-matching in the grounding validator.
- **A refunded visit still counts toward `total_billed`.** Billing is a historical fact; a refund is a separate event layered on top, not a rewrite of history. This means `total_collected` can legitimately go negative on a heavy-refund day.
- **`outstanding_paise` only ever comes from non-refund visits.** A refund is closed/settled — it can never also be "still owed."
- **Analytics (revenue-by-hour, top medicines) excludes refund line items entirely.** Analytics measures genuine business activity ("what moved, when"); a refund line item reverses a past sale, it doesn't represent new activity today.
- **The grounding validator is plain deterministic Python (regex + set membership), not a second LLM call.** The brief says grounding is "graded automatically" — a second model's judgment is still probabilistic; code you can unit-test is a stronger guarantee.

## Data consistency upon update

`log_id` is deterministic: `f"{clinic_id}-{log_date}"`. Re-uploading the same clinic-day (e.g. a corrected file) maps to the *same* `log_id` — it's an upsert, not a duplicate insert.

`LogRepository.upsert_log()` wraps its delete-then-insert sequence (across `billing_logs`, `visits`, `line_items`) in a single SQLite transaction using Python's `with connection:` idiom, which commits on clean exit and **rolls back on any exception**. This means a partial failure mid-write (e.g. the process dies after deleting old visits but before inserting all new ones) leaves the previous data untouched, rather than corrupting the log into a half-written state. Consistency comes from atomicity, not from careful step-ordering.

This is directly tested in `backend/tests/test_api.py::test_reupload_same_clinic_day_upserts_not_duplicates` — it re-uploads a corrected file for the same day and asserts: same `log_id`, exactly one row in `GET /api/logs` (no duplicate), and reconciliation reflecting only the new numbers (not old+new summed).

## API Contract

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/logs` | `POST` | Ingest a billing log (raw JSON array of visit rows). Partial success supported — valid rows are stored, malformed rows are reported with row index + field + reason. Returns `422` only if *every* row is malformed. |
| `/api/logs` | `GET` | List ingested clinic-days (lightweight, for the sidebar). |
| `/api/logs/{log_id}/reconciliation` | `GET` | Deterministic reconciliation report. `404` if the log doesn't exist. |
| `/api/logs/{log_id}/analytics` | `GET` | Deterministic analytics report. `404` if the log doesn't exist. |
| `/api/logs/{log_id}/narrative` | `POST` | Generate (or regenerate) the AI narrative + grounding check, cache it. |
| `/api/logs/{log_id}/narrative` | `GET` | Return the cached narrative. `404` if none has been generated yet. |

### `POST /api/logs` response shape

```json
{
  "log_id": "CLN-KNP-014-2026-07-25",
  "clinic_id": "CLN-KNP-014",
  "log_date": "2026-07-25",
  "total_rows": 3,
  "valid_count": 3,
  "rejected_count": 0,
  "errors": [
    { "row_index": 1, "issues": [{ "field": "payment_mode", "reason": "..." }], "raw_row": { ... } }
  ]
}
```

### `POST/GET /api/logs/{log_id}/narrative` response shape

```json
{
  "log_id": "CLN-KNP-014-2026-07-25",
  "narrative": "₹42,850 billed across 18 visits...",
  "cited_figures": [
    { "value": "42,850", "source_field": "total_billed_paise" }
  ],
  "grounding_status": "llm_grounded",
  "generated_at": "2026-08-15T04:51:57.12Z"
}
```

`grounding_status` values: `llm_grounded`, `llm_retry_grounded`, `fallback_no_llm_configured`, `fallback_malformed_response`, `fallback_ungrounded_after_retry`.

## Running locally

**Backend:**
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
# API docs at http://localhost:8000/docs
```

To enable real AI narratives (optional — the app works fine without this, using the deterministic fallback template):
```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

**Frontend:**
```bash
cd frontend
npm install
cp .env.example .env   # set VITE_API_BASE_URL if backend isn't on localhost:8000
npm run dev
```

**Tests:**
```bash
cd backend
python3 -m pytest tests/ -v
```

## Deployment

**Backend (Render):**
1. Push this repo to GitHub.
2. In Render, "New Web Service" → connect the repo → set root directory to `backend`.
3. Render will pick up `backend/render.yaml` automatically (build: `pip install -r requirements.txt`, start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`).
4. Set `ANTHROPIC_API_KEY` in the Render dashboard's environment variables (optional — omit to run in fallback-template-only mode).
5. Note the deployed URL, e.g. `https://swasthiq-backend.onrender.com`.

**Frontend (Vercel):**
1. In Vercel, "Add New Project" → import the repo → set root directory to `frontend`.
2. Framework preset: Vite (auto-detected).
3. Add environment variable `VITE_API_BASE_URL` = your Render backend URL from above.
4. Deploy. `vercel.json` is already set up for SPA routing.

Note: Vite bakes `VITE_API_BASE_URL` in at **build time**, not runtime — if you change the backend URL later, trigger a new frontend deploy, don't just restart it.