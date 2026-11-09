# Write Better

A free web app for a language school's teachers and adult students. Students write; an AI model drafts grammar feedback; the teacher reviews and edits every draft before the student sees it. There are four kinds of user: admin, teacher, student, and visitors to the public pages.

The app is being rebuilt from a single-teacher app. Read `docs/BUILD_PLAN.md` first: it holds the decisions, the accepted defaults, and the phases. The other files in `docs/` still describe the single-teacher app until the phase that changes them updates them.

## Commands

```sh
python3.12 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt   # once
.venv/bin/python -m pytest                                                   # all tests, no cloud access needed
cd web && npm ci --ignore-scripts && npm run build                           # frontend type-check and build
```

Running the app locally is described in `README.md`. CI (`.github/workflows/tests.yml`) runs the tests and the frontend build on every push.

## Stack
Python 3.12 + FastAPI + Pydantic for the API and the AI service ("harness"), two Cloud Run services. React frontend with plain CSS. Firestore, Cloud Storage, Identity Platform. Claude via Vertex AI, with Gemini 3.8 Flash (also Vertex) as an automatic fallback when Claude is unavailable. Google Cloud only, US East.

## Rules that must never be broken
- The harness has no database or storage access and is never given usernames or unscrubbed student text. Photos go to `transcribe` only.
- Clients never access Firestore or Storage directly; all authorization is server-side in the API.
- A teacher only ever reaches their own classes, students and work. Another teacher's records answer "not found".
- The admin manages accounts and spending, and never reaches student work or teacher notes.
- A signed-in account with no role (a pending teacher sign-up) reaches nothing except its own sign-up request and status (`api/app/signup.py`).
- Only the admin reaches `/admin` routes. They return account details and counts, never student records or writing.
- Students see only their own work, and only after the teacher releases it. That includes the student error view.
- Passwords go only to Identity Platform; the API never stores or logs them.
- Original student text is never modified; only the teacher-edited scrubbed copy is sent to the harness.
- Never log student text or images.
- Validate all harness output in the API; never show invalid output to the teacher.
- Total cost must stay under $20/month; the AI spend cap (Claude and Gemini) is enforced in the app.
- Scope is grammar, punctuation, spelling, capitalization only. No numeric scores, percentages or grades anywhere.
- Public pages and user-facing text use the name "Write Better" and don't name any school.

## Working style
- The owner reads Python, not TypeScript/React: keep backend code clear, typed, and commented where non-obvious.
- Work phase by phase per `docs/BUILD_PLAN.md`. Stop at the end of each phase and report to the owner before starting the next.
- Commit as you go and push at least at the end of each phase. Mark live-only features `NOT YET TESTED LIVE` until tested on the deployment.
- The plan's "Assumptions" are accepted defaults. Ask before deviating from them or from any other decision in the plan. Items marked [VERIFY] must be confirmed, not assumed.
- Prefer the simplest approach that meets the requirements; do not add services or dependencies without asking.

## Keep code minimal
Before writing code, work down this list and stop at the first step that works:
1. Does this need to exist? If not, skip it.
2. Does the codebase already have it? Reuse it.
3. Does the standard library or the platform do it?
4. Is there an already-installed dependency that does it?
5. Otherwise write the smallest thing that works.

- Read the code a change touches before editing it.
- Prefer a short, readable solution over a clever one-liner; the owner reads the Python.
- No speculative features, abstractions, or config for needs that don't exist yet.
- Ask before adding a new dependency or service.
- If the project already has a component, utility, or pattern for something, use it instead of the native or generic alternative.

**These rules never override the "Rules that must never be broken" section above.** Authorization and ownership checks, harness output validation, the original-versus-scrubbed separation, privacy-safe logging, and the spend cap are required code, not over-engineering. Never remove or skip them to make code shorter.
