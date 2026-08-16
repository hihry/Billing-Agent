# SwasthiQ — EOD Billing & Analytics Agent

A clinic billing reconciliation, analytics, and AI-narrative tool — built for the SwasthiQ SDE Intern take-home assignment (July 2026).

**Live demo:** `<add your Vercel URL here after deploying>`
**Backend API docs:** `<add your Render URL here>/docs`

```
backend/    Python REST API — FastAPI + SQLite
frontend/   React app — Vite
```

---

## What this does

A clinic's front desk logs every transaction through the day — consultations, medicine sales, refunds, partial payments. This tool ingests that log and produces, on demand:

1. An end-of-day reconciliation: billed vs. collected vs. outstanding vs. refunds, split by payment mode.
2. Analytics: revenue by hour of day (with peak hour called out), and medicines ranked two ways — by quantity moved and by revenue.
3. An AI-generated, WhatsApp-ready plain-language summary of both — with every number in it traceable back to the deterministic report it came from.

---

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Backend API | FastAPI | Async-friendly, automatic OpenAPI docs, strong Pydantic integration |
| Data validation | Pydantic v2 | Single source of truth for what a "valid row" means, reused across parsing/storage/API |
| Database | SQLite (raw SQL, no ORM) | Brief explicitly asks for lightweight storage — "pipeline and API design, not infra plumbing" |
| LLM provider | OpenRouter (free-tier model) | Any LLM API is acceptable per the brief; OpenRouter gives free access without requiring a paid key |
| Frontend | React + Vite | Fast dev loop, standard SPA tooling |
| Charts | Recharts | Straightforward bar chart with per-bar coloring for the peak-hour highlight |

---

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

1. **Deterministic layer** (`backend/app/engine/`) — pure arithmetic over validated `Visit` objects. Never imports anything LLM-related. This is the ground truth everything else is checked against.
2. **Persistence layer** (`backend/app/storage/`) — SQLite, raw SQL. See "Data consistency on update" below.
3. **Narrative layer** (`backend/app/narrative/`) — an LLM writes a WhatsApp-style summary of the deterministic report. Every number in that summary is checked against a whitelist built from the report itself before it's ever shown to a user. If the LLM is unavailable, its response is malformed, or it can't produce a grounded summary after one retry, a deterministic template (grounded by construction, zero LLM involvement) is used instead — the narrative endpoint never fails to return *something* usable.

---

## Key design decisions

Documented here since the brief asks for the reasoning behind the pipeline, not just the code:

- **Money is stored as integer paise throughout, never float rupees.** Floats introduce rounding drift that would break exact-number-matching in the grounding validator.
- **A refunded visit still counts toward `total_billed`.** Billing is a historical fact; a refund is a separate event layered on top, not a rewrite of history. This means `total_collected` can legitimately go negative on a heavy-refund day — that's correct, not a bug.
- **`outstanding_paise` only ever comes from non-refund visits.** A refund is closed/settled — it can never also be "still owed."
- **Analytics (revenue-by-hour, top medicines) excludes refund line items entirely.** Analytics measures genuine business activity ("what moved, when"); a refund line item reverses a past sale rather than representing new activity.
- **The grounding validator is plain deterministic Python (regex + set membership), not a second LLM call.** The brief says grounding is "graded automatically" — a second model's judgment is still probabilistic; code that's unit-tested is a stronger guarantee than an LLM checking another LLM.
- **`log_id` is deterministic (`{clinic_id}-{log_date}`), not a random UUID.** This is what makes re-uploading a corrected file behave as an upsert rather than creating a duplicate — see below.

---

## Data consistency upon update

Re-uploading the same clinic-day's file (e.g. a corrected version) maps to the *same* `log_id`, since it's derived deterministically from `clinic_id` + `log_date` rather than randomly generated. This makes it an upsert, not a duplicate insert.

`LogRepository.upsert_log()` wraps its delete-then-insert sequence (across `billing_logs`, `visits`, `line_items`) in a single SQLite transaction using Python's `with connection:` idiom, which commits on clean exit and **rolls back on any exception**. A partial failure mid-write (e.g. the process dies after deleting old visits but before inserting all the new ones) leaves the *previous* data untouched rather than corrupting the log into a half-written state. Consistency comes from atomicity, not from careful step-ordering.

This is directly tested in `backend/tests/test_api.py::test_reupload_same_clinic_day_upserts_not_duplicates`: it re-uploads a corrected file for the same day and asserts the same `log_id` is reused, exactly one row appears in `GET /api/logs` (no duplicate), and reconciliation reflects only the new numbers — not old+new summed together.

---

## API Contract

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/logs` | `POST` | Ingest a billing log (raw JSON array of visit rows). Partial success supported — valid rows are stored, malformed rows are reported individually with row index + field + reason. Returns `422` only if *every* row in the file is malformed. |
| `/api/logs` | `GET` | List ingested clinic-days (lightweight — id, date, visit count — for the sidebar). |
| `/api/logs/{log_id}/reconciliation` | `GET` | Deterministic reconciliation report. `404` if the log doesn't exist. |
| `/api/logs/{log_id}/analytics` | `GET` | Deterministic analytics report. `404` if the log doesn't exist. |
| `/api/logs/{log_id}/narrative` | `POST` | Generate (or regenerate) the AI narrative, run the grounding check, cache the result. |
| `/api/logs/{log_id}/narrative` | `GET` | Return the cached narrative. `404` if none has been generated yet for this log. |

Full interactive docs (request/response schemas, try-it-out) are auto-generated by FastAPI at `/docs` on any running instance.

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
    { "row_index": 1, "issues": [{ "field": "payment_mode", "reason": "..." }], "raw_row": { "...": "..." } }
  ]
}
```

### `POST` / `GET` `/api/logs/{log_id}/narrative` response shape

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

`grounding_status` reflects exactly which path produced the narrative:

| Value | Meaning |
|---|---|
| `llm_grounded` | The LLM's first attempt passed the grounding check as-is. |
| `llm_retry_grounded` | First attempt had an invented number; the retry (told exactly which number was wrong) passed. |
| `fallback_no_llm_configured` | No `OPENROUTER_API_KEY` set — deterministic template used. |
| `fallback_malformed_response` | The LLM's response wasn't valid/parseable JSON, or the report data itself was malformed — deterministic template used. |
| `fallback_ungrounded_after_retry` | The LLM invented a number on both attempts — deterministic template used. |

---

## Running locally

**Backend:**
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
# interactive API docs at http://localhost:8000/docs
```

To enable real AI narratives (optional — the app works fully without this, using the deterministic fallback template):
```bash
export OPENROUTER_API_KEY=sk-or-...
# optional: export OPENROUTER_MODEL=liquid/lfm-2.5-2.6b:free   (this is the default)
```

To debug a 500 error, temporarily surface the real traceback in the API response body:
```bash
export SWASTHIQ_DEBUG=1   # NEVER set this in a real deployment — it leaks stack traces
```

**Frontend:**
```bash
cd frontend
npm install
cp .env.example .env   # set VITE_API_BASE_URL if the backend isn't on localhost:8000
npm run dev
```

**Tests:**
```bash
cd backend
python3 -m pytest tests/ -v
```

---

## Deployment

**Backend → Render**
1. Push this repo to GitHub.
2. Render → New → Web Service → connect the repo → set root directory to `backend`.
3. Render auto-detects `backend/render.yaml` (build: `pip install -r requirements.txt`, start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`).
4. Set `OPENROUTER_API_KEY` in the Render dashboard's Environment tab (optional — get a free key at https://openrouter.ai/keys; omit to run in fallback-template-only mode).
5. Note the deployed URL, e.g. `https://swasthiq-backend.onrender.com`. Confirm it's live by visiting `/docs`.

**Frontend → Vercel**
1. Vercel → Add New → Project → import the same repo → set root directory to `frontend`.
2. Framework preset: Vite (auto-detected).
3. Add environment variable `VITE_API_BASE_URL` = your Render backend URL from above (no trailing slash).
4. Deploy. `frontend/vercel.json` is already configured for SPA routing.

**Two gotchas worth knowing before you deploy:**
- Vite bakes `VITE_API_BASE_URL` in at **build time**, not runtime. If you change the backend URL later, you must trigger a new frontend deployment — restarting isn't enough.
- Render's free tier spins down after inactivity; the first request after idle can take 30–60 seconds to wake up. If a live demo looks stuck loading, that's why — send one "warm-up" request beforehand.

---

## Testing

88 backend tests across ingestion validation, the deterministic engine, SQLite persistence/upsert consistency, the grounding validator, the narrative orchestration (including a scripted fake LLM client to test retry/fallback logic deterministically, with no network access needed), and full HTTP integration tests via FastAPI's `TestClient`. Several tests run against real sample data provided by SwasthiQ (not just synthetic fixtures) — see `backend/tests/test_real_data_july25.py`, which locks in behavior for a genuine edge case: a day where every visit is a refund.

```bash
cd backend
python3 -m pytest tests/ -v
```

---

## Known limitations

- The grounding validator matches purely on digits, with no concept of units — a rupee amount that happens to equal a visit count or medicine quantity (e.g. exactly ₹500 vs. "500 visits") could theoretically produce a coincidental whitelist collision. Mitigated by `cited_figures`, which forces the LLM to declare which report field each number came from, giving a reviewer something concrete to check even when raw digits happen to line up. Documented and tested in `backend/tests/test_grounding.py::test_known_limitation_coincidental_numeric_collision`.
- Free-tier LLM models (via OpenRouter) can be less reliable at strict JSON-only output than larger paid models — this is precisely why the retry-once-then-fallback machinery exists rather than trusting the first response.