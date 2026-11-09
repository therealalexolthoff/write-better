# Web app (React)

Screens only - every rule (who may see what, grading, validation) lives in
the Python API. Built into `web/dist` and served by the API in production.

## Local development

Needs Node 20.19+ (or 22.12+). Three terminals from the repo root:

1. Harness, mock mode: `HARNESS_MOCK_MODE=true .venv/bin/uvicorn harness.app.main:app --port 8001`
2. API: `FIREBASE_API_KEY=... FIREBASE_AUTH_DOMAIN=<project>.firebaseapp.com FIRESTORE_EMULATOR_HOST=localhost:8085 FIRESTORE_PROJECT_ID=demo .venv/bin/uvicorn api.app.main:app --port 8000`
   (with `scripts/dev_firestore_emulator.sh` running for the emulator)
3. Web: `cd web && npm install --ignore-scripts && npm run dev`, then open http://localhost:5173

Sign-in uses the real Identity Platform project (there is no local auth
emulator in this setup).

## Screen preview (design work, no sign-in needed)

`npm run dev`, then open http://localhost:5173/preview.html. It lists every
screen, shown with made-up sample data: no API, database or sign-in needed.
Add `&width=390` to see a screen at phone width. The preview is
development-only (`src/preview/`, `preview.html`): it is never built into
`web/dist` or served by the API.

## Pages

`src/router.tsx` maps the address bar to a page: `/` home, `/privacy`,
`/sign-in`, and `/app` (the signed-in app). The API serves `index.html` for
each of these (`PAGES` in `api/app/main.py`; a test keeps the two lists in
step).

## Design system

All styling is in `src/styles.css`: colour tokens at the top (the school's
burgundy and cyan), then layout, components and pages. Text colours meet
WCAG AA contrast; the bright cyan is decoration only.
