# Write Better

A free web app that helps adult language learners write better English. Students write, or photograph their handwriting; an AI model drafts feedback on grammar, punctuation, spelling and capitalization; and the teacher reviews and edits every draft before the student sees it.

The AI drafts; the teacher decides. Nothing the AI produces reaches a student without the teacher's approval.

> **Status: being built.** Write Better is being rebuilt from a single-teacher app. Until Phase 1 of `docs/BUILD_PLAN.md` is done, the code still contains that app's grammar exercises and lessons, and it supports only one teacher. The plan lists every phase.

## What it will do

**Public pages**
- A home page explaining the tool, a privacy page, sign-in, and a teacher sign-up form (name, email and password). New teacher accounts do nothing until the admin approves them.

**For the admin**
- Approve or reject teacher sign-ups, manage teacher accounts, transfer a teacher's classes, and watch AI spending against a monthly cap. The admin never sees student work.

**For teachers** (laptop-first)
- Create classes and student accounts, and assign writing to a whole class or chosen students.
- Upload photos of handwritten work. The AI transcribes it verbatim, mistakes included, and the teacher corrects the transcription side by side with the photos.
- Review AI feedback marked against a fixed set of 14 error codes (spelling, punctuation, capitalization, verb tense, articles, prepositions and so on). Accept, edit, recode or override every mark and comment, then release it.
- See a learner profile for each student, worked out from approved feedback only, and keep private notes.
- Each teacher sees only their own classes and students.

**For students** (phone-first)
- Write with autosave that survives app switching or lost signal, or add photos of handwritten pages.
- See results with each error marked by its code, then revise: tap a flagged part and retype just those words.
- See a chart of their own errors across all their returned work, with examples from their writing.
- No numeric scores, percentages or grades anywhere.

**Scope:** grammar, punctuation, spelling and capitalization only. The AI is told not to comment on style, word choice, content or organization.

## Privacy and safety by design

- **Scrubbing.** Before any student text goes to the AI, the teacher edits a separate "scrubbed" copy to remove names and personal details. Only that copy is sent; the original is never modified or sent anywhere. Handwriting photos are the one exception, sent for transcription only.
- **Opaque ids.** Students are known to the AI only by a random id, never by username.
- **No direct database access.** Browsers never touch the database or file storage; every request goes through the API, which checks who is asking. Firestore rules deny all client access, and photos are viewable only through 15-minute signed links.
- **Validated output.** Every AI result is checked against a strict schema, and flagged errors must point at real text, in both the AI service and the API. Invalid output is never shown.
- **Prompt-injection resistant.** Student text is passed to the model as clearly marked data, never as instructions.
- **No student text in logs.** Logs contain ids, counts and error types only.
- **Spend cap.** AI spend is capped per month inside the app and checked before every call, with email alerts as it nears the cap.

## How it fits together

```
Phone / laptop (React)
        |  HTTPS, signed in with Identity Platform
        v
  API service (Cloud Run, FastAPI) ---> Firestore (all data)
        |                         \---> Cloud Storage (private; handwriting photos)
        v  private, service-account-only
  Harness service (Cloud Run, FastAPI) ---> Claude on Vertex AI
                                            (Gemini fallback if Claude is unavailable)
```

- **API** (`api/`): all business logic, authorization, grading, scrubbing, the spend cap and the learner profile. It also serves the built frontend.
- **Harness** (`harness/`): a stateless AI service. It has five operations today: generate exercise, transcribe, evaluate exercise, evaluate writing, and generate lesson. Phase 1 cuts it to transcribe and evaluate writing. It has no database or storage access.
- **Shared** (`shared/`): the schemas, the 14-code error taxonomy and the validation that both services use.
- **Web** (`web/`): the React frontend. It only collects input; every rule lives in the Python API.

Stack: Python 3.12, FastAPI, Pydantic v2, React 19, Vite, Firestore, Cloud Storage, Identity Platform, and Claude via Vertex AI (Gemini as a fallback), all on Google Cloud.

## Repository layout

| Path | Contents |
|---|---|
| `api/` | API service and its tests |
| `harness/` | AI service, prompt templates, and its tests |
| `shared/` | Schemas, error taxonomy, validation, privacy-safe logging |
| `web/` | React frontend |
| `infra/` | Google Cloud setup, Firestore rules, monitoring alerts |
| `scripts/` | Test runner, Firestore emulator, golden-set evaluation |
| `golden/` | Reference passages for measuring AI accuracy |
| `docs/` | Requirements, architecture, AI service spec, build plan, security review |

## Running locally

**Requirements:** Python 3.12, Node.js 20.19+ (or 22.12+), and the gcloud CLI with the Firestore emulator (`gcloud components install cloud-firestore-emulator`).

**1. Install**

```sh
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cd web && npm install --ignore-scripts && cd ..
```

**2. Start the pieces**, each in its own terminal from the repo root:

```sh
# Firestore emulator
./scripts/dev_firestore_emulator.sh

# Harness in mock mode: canned, schema-valid AI responses, no AI calls or costs
HARNESS_MOCK_MODE=true .venv/bin/uvicorn harness.app.main:app --port 8001

# API, pointed at the emulator and the local harness
FIREBASE_API_KEY=<key> FIREBASE_AUTH_DOMAIN=<project>.firebaseapp.com \
FIRESTORE_EMULATOR_HOST=localhost:8085 FIRESTORE_PROJECT_ID=demo \
.venv/bin/uvicorn api.app.main:app --port 8000

# Frontend dev server, which forwards API calls to port 8000
cd web && npm run dev
```

Then open http://localhost:5173.

Notes:
- Sign-in uses a real Identity Platform project; there is no local auth emulator in this setup. The teacher account needs TOTP multi-factor authentication and a `teacher` role claim (see `infra/README.md`). Student accounts are created from inside the app.
- Photo upload needs a real Cloud Storage bucket: set `PHOTO_BUCKET` on the API.
- To use a real model instead of mock mode, run the harness with `HARNESS_MOCK_MODE=false` and `VERTEX_PROJECT_ID=<project>`, using credentials that can call Vertex AI.

## Tests

```sh
.venv/bin/python -m pytest
```

The tests cover both services and the shared code. They run without any cloud access: Firestore, storage, sign-in and the AI service are replaced with in-memory fakes. They check authorization (every endpoint refuses a request with no login, and students can't see each other's work or teacher-only fields), grading, AI output validation, the scrubbed/original separation, the spend cap, privacy-safe logging, and prompt-injection handling.

## Deploying to Google Cloud

`infra/setup_gcp.sh` creates the project resources: APIs, Firestore with daily backups kept 7 days, the private photo bucket, service accounts, and both Cloud Run services. `infra/README.md` walks through the steps, including the manual Identity Platform setup and requesting Vertex AI model access, which can take a while to be approved.

After setup:
- `infra/deploy_firestore_rules.py` deploys the deny-all Firestore rules.
- `infra/monitoring.sh` creates email alerts for failed AI calls, server errors and AI spend.

The app is designed to stay under $20 a month in total, AI included, with a hard AI spending cap enforced in the app.

## Measuring AI accuracy

`scripts/golden_set.py` runs the AI evaluation on a set of passages annotated by a teacher. It reports precision (how many of the AI's flags the teacher also flagged), recall (how many of the teacher's flags the AI found), and code agreement. Run it after any prompt or model change.

`golden/synthetic.json` is a labelled placeholder set; replace it with real annotated passages. Keep real passages in `golden/private/`, which git ignores.

## Documentation

- `docs/REQUIREMENTS.md`: what the app does, requirement by requirement
- `docs/ARCHITECTURE.md`: data model, submission pipeline, authorization
- `docs/HARNESS_SPEC.md`: AI operations, schemas, and the 14 error codes
- `docs/SECURITY_REVIEW.md`: what was checked, how, and known limits
- `docs/BUILD_PLAN.md`: the phased build plan
