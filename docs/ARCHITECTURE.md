# Architecture (v1)

> **Status:** updated in Phase 5 (2026-11-09): admin, teacher and student roles, teacher ownership on every record, teacher sign-up and the admin's account management, classes, and the student's error view. Assignments are added to the data model in Phase 6 (see `docs/BUILD_PLAN.md`). Where they disagree, the build plan wins.

## 1. Overview
```
Student phone / Teacher or admin laptop
        |  HTTPS (React SPA, session via Identity Platform ID token)
        v
  API service (Cloud Run, Python/FastAPI)  ----> Firestore (all data)
        |                |                 \--> Cloud Storage (private; handwriting photos)
        |                \--> Identity Platform (auth)
        v  (private, service-account-only invoke)
  Harness service (Cloud Run, Python) ----> Claude on Vertex AI
```
All business logic and authorization live in the API. The harness has **no** database or storage access; it receives a payload and returns validated JSON.

## 2. Stack
- Frontend: React SPA (responsive; student screens phone-first, teacher screens laptop-first). No native app, no PWA.
- API and harness: Python 3.12, FastAPI, Pydantic v2. Two separate Cloud Run services.
- Database: Firestore (native mode). Auth: Google Identity Platform. Files: Cloud Storage. Model access: Vertex AI (Claude; Gemini 3.8 Flash as automatic fallback when Claude is unavailable — see HARNESS_SPEC section 8), authenticated by service account (no API keys).
- Region: **confirmed** — `us-east4`/`us-east5` do not support current Claude models as fixed regional Vertex endpoints (only `us-east5` serves Sonnet 4.6 and earlier, now stale). Use the **`us` multi-region endpoint** instead: keeps data in the US, works with current models, 10% price premium over the region-free `global` endpoint.
- Frontend hosting: serve the built SPA from the API service (simplest), or Firebase Hosting / Cloud Storage; agent picks the simplest that works.

## 3. Key decisions
1. **Clients never touch Firestore or Storage directly.** Firestore/Storage rules deny all client access. Autosave is a debounced API call. No realtime features.
2. **Harness is a separate private service** with two operations (transcribe, evaluate_writing) and no data access. Swappable model/provider.
3. **Learner profile is computed by plain code** from approved data. The harness never sees it.
4. **Harness calls are synchronous** with a persisted job record (no queue). Failure leaves a retryable job. Revisit Cloud Tasks only if latency becomes a problem.
5. **Identity Platform kept** (not custom auth): hardened password handling, brute-force protection, built-in TOTP. Students use a synthetic email `<username>@students.internal` created and hidden inside one function (confirmed: Identity Platform does not validate the domain, only that the string is a syntactically unique email); teachers and the admin use a real, **verified** email + TOTP — confirmed verified email is a hard prerequisite for MFA enrollment, which only applies to them since students never enroll in MFA. The role (`admin`, `teacher` or `student`) is a custom claim on the account; an account without one is refused everywhere.
6. **Original vs scrubbed text are separate fields.** Only scrubbed text leaves the API.
7. **Strict validation** of all harness output; the API never trusts the harness.
8. **Hard spend cap in the app** (Google budgets only alert).
9. **Opaque IDs**: each student has a random ID (not derived from username). Usernames and teacher notes never go to the harness.
10. **Teacher ownership on every record.** Each student, exercise, submission and job record stores `teacher_id` (the owning teacher's account uid). Ownership checks run before each route reads its request (`api/app/access.py`).

## 4. Data model (Firestore)
| Collection | Contents |
|---|---|
| `classes` | id, **teacher_id**, name, archived, created_at (`api/app/classes.py`). |
| `students` | id (opaque), username, auth uid, **teacher_id**, class_id, active, teacher_notes, created_at. The profile is not stored; it is computed on demand from approved submissions (`api/app/profile.py`), so it can never drift from its data. teacher_notes is one private free-text field, never sent to the harness. |
| `exercises` | id (same as its submission), student_id, **teacher_id**, kind (`writing`), status (always `assigned`), title, prompt, min/max words, teacher_request, created_at, assigned_at |
| `submissions` | id, exercise_id, student_id, **teacher_id**, state, answers (`{"text": ...}`, the original), scrubbed_answers, final_source (`typed`/`photo`), transcription, photos[] (path, uploaded_at, uploaded_by `teacher`/`student`), evaluation and evaluation_ai (annotations with computed offsets, comment), evaluation_valid, release_at, revision {edits, submitted_at, outcomes} |
| `jobs` | id, operation, student_id, **teacher_id**, prompt_version, model, status, latency, tokens_in/out/cached, cost, validation_outcome (`passed`/`rejected`), teacher_action (`accepted`/`edited`/`regenerated`), error |
| `teachers` | id (= auth uid), name, email, active, source (`signup`/`admin`), created_at. Written by the admin's routes (`api/app/admin.py`). |
| `signup_requests` | id (= auth uid), name, email (from the signed-in token), status (`pending`), created_at, day (for the daily limit). Deleted when the admin approves or rejects it, or after 30 days. |
| `spend` | month key, totals |
| `settings` | single doc: monthly_cap, per-operation model names, alert thresholds, profile_window (default 5), token budgets |
| `audit` | actor, action, target, timestamp |

Subcollections are fine where natural (e.g. submissions under students) if it simplifies queries; the agent decides.

## 5. Submission pipeline
```
assigned -> in_progress -> scrub_review                       (typed)
assigned/in_progress -> transcribing -> transcript_review -> scrub_review   (handwritten)
scrub_review -> evaluating -> draft_ready -> ready_to_release
ready_to_release -> released                                 (nothing flagged)
ready_to_release -> revision_open -> revision_submitted -> revision_reviewed
```
- Reopen (teacher only): back to `in_progress`, audit-logged.
- Editing scrubbed text after `draft_ready` sets `evaluation_valid=false` and returns to `scrub_review`.
- Errors in any harness step: job status `error`, submission stays in its prior state, retry available.

## 6. Authorization
- Student: may read/write only their own assigned, unsubmitted answers and their own photo pages on them (signed URLs, until submit); read own released results and their own error view (`GET /me/errors`, released work only); submit revision when open.
- Teacher: only their own students and their work (records whose `teacher_id` is theirs), except impersonation. Another teacher's record answers "not found". Photos only via signed URLs generated by the API.
- Admin: account management (`/admin` routes: sign-ups and teachers) and, from Phase 7, spending. Refused by every route that reaches students or their work; the admin routes return account details and counts only.
- An account with no role (a pending teacher sign-up) reaches only its own sign-up request and status (`/signup`).
- Teachers and the admin must sign in with their authenticator code; until they have one, the app shows only the account setup (verify email, add the app).
- Every endpoint checks role and ownership server-side, before reading the request body (`api/app/access.py`). `api/tests/test_teacher_isolation.py` walks every endpoint as another teacher, the admin, and other students. Student endpoints never return teacher-only fields (corrections, explanations on annotations, notes, original-vs-scrubbed, unreleased drafts).

## 7. Context assembler
Removed in Phase 1: it fed exercise and lesson generation, which no longer exist.

## 8. Cost control and observability
- Per call: estimate cost before, enforce cap, record actual after. Show monthly spend to the admin (Phase 7).
- Job records capture operation, prompt version, model, latency, retries, tokens, cost, validation outcome, and teacher action (accepted/edited/regenerated). Edit rate per operation and prompt version is the main quality signal.
- Structured JSON logs to Cloud Logging with IDs and counts only (never student text/images). Cloud Monitoring alerts: harness error rate, spend thresholds. Billing alerts at $10/$15.
- No third-party LLM tracing tools (they would receive student text).
- Prompt caching for the static prompt prefix — confirmed supported on Vertex for Claude models (in-memory cache, 24-hour TTL).

## 9. Backups and deletion
Firestore scheduled backups with 7-day retention. Student deletion removes Firestore documents, Storage photos, and the Identity Platform user; deleted data may persist in backups up to 7 days, stated on the confirmation screen.

## 10. Environments and deployment
Single production GCP project. Local development uses the Firestore emulator and the harness in mock mode. Deploy with `gcloud run deploy` scripts (or a small Cloud Build config); infrastructure setup documented in a script/README so it is repeatable.

Confirmed setup requirements for the project setup script:
- Request Vertex AI Model Garden access for the Claude model early (no fixed approval SLA observed) — do this before anything else depends on it.
- Grant the API service's Cloud Run runtime service account the `roles/iam.serviceAccountTokenCreator` role **on itself** (self-impersonation) — required for signed URL generation via IAM `signBlob`; easy to miss since it's self-referential rather than a grant on another resource.
- Firestore native backup schedules: `gcloud firestore backups schedules create --database=DATABASE_ID --recurrence=daily --retention=7d` (confirmed supported, up to 14 weeks max retention).

## 11. Estimated monthly cost (confirmed)
_Modelled for the single-teacher app, before Phase 1 removed exercise and lesson generation; Write Better makes fewer AI calls per student. Re-check against real job records._

Cloud Run, Firestore, Identity Platform, Storage: within free tiers at this scale (Identity Platform free up to 50k MAU; TOTP MFA has no per-verification cost). Claude usage (model: `claude-sonnet-5` for all operations, `us` multi-region endpoint), modeling ~1 exercise generated + ~0.7 evaluations + ~0.5 lessons + ~0.25 photo transcriptions per student per week:
- 8 students: ~$1-4/month
- 30 students: ~$5-15/month (padded for regenerations/retries)

Both stay under the $20 total cap with margin; the app's hard cap plus $10/$15 billing alerts remain the safety net for heavier-than-modeled use. Re-check this estimate once real usage data exists.
