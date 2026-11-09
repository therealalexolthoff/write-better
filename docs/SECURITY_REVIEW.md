# Security review (Phase 8, 2026-11-09)

What protects Write Better, how each item was verified, and what's left. Re-check after any change to roles, routes, storage, logging, prompts or the deployment. "Live" means checked against write-better-app with `scripts/live_test.py`, `scripts/browser_test.mjs` or direct requests.

## Fixed in this review

- **No security headers.** Every response now carries a Content-Security-Policy (scripts only from the app; no other site may frame it), HSTS, `nosniff`, a referrer policy and a permissions policy (`api/app/security_headers.py`). Verified by `api/tests/test_health.py`, live headers, and no policy violations in Chrome on any page or through the whole sign-in journey.
- **A taken student username crashed the request (500).** It now answers 409 with a plain message (`api/tests/test_students.py`).
- **Unbounded scaling.** Cloud Run instances are capped (API 3, harness 2), which also caps what a flood of requests can cost.
- **Email links didn't work.** Links the admin hands out (teacher setup, password resets, the admin's own) pointed at Google's hosted page with no key, and the sign-in key was locked to the app's address. Those links now open the app's own `/account-action` page with just the one-time code (`identity.action_link_path`). Verification emails still use Google's hosted page (Identity Platform refuses to change that link: `EMAIL_TEMPLATE_UPDATE_NOT_ALLOWED`), so the key also allows `write-better-app.firebaseapp.com`, Google's page for this project. Verified live by `scripts/browser_test.mjs`.

## Checked and in place

| Area | How it's protected | How it was verified |
|---|---|---|
| Every endpoint checks who is calling | Each route depends on a role check; tokens are verified with revocation checks, so disabled accounts are refused at once. | `test_every_route_needs_login.py` walks every published endpoint. Live: no login → 401. |
| Teachers kept separate | Every class, assignment, student, exercise, submission and job record carries `teacher_id`. Ownership checks (`api/app/access.py`) run before a route reads its request; another teacher's record answers "not found". | `test_teacher_isolation.py` walks every endpoint as another teacher, the admin, another teacher's student and another student, checking status, unchanged data and no leaks. Removing a check on purpose was caught each time (Phases 2, 5, 6). Live: a second teacher got 404 on the first teacher's student, exercise, assignment, class overview and photos, and empty lists. |
| The admin never reaches student work | Admin routes return account details, counts and dollars only; every student-work route refuses the admin. | Isolation walk; `test_admin.py`, `test_spending.py`. Live: 403. |
| Admin routes are admin-only | `/admin` routes require the admin role and the authenticator code. | Isolation walk as teachers and students. |
| Authenticator code for admin and teachers | Enforced by the API from the token's second-factor claim, not just the sign-in screen. Emails must be verified before an authenticator can be added. | Tests; live: an approved teacher with no authenticator is refused; the browser journey enrolls via the QR/key and signs in with a code. |
| Pending sign-ups reach nothing | A login with no role reaches only its own sign-up request and status. | Isolation test; live 401. |
| Sign-up abuse | The email comes from the verified token, never the form (extra fields are refused); a hidden bot field; a daily limit of 20; Identity Platform's own limits; an alert email per sign-up; nothing works until the admin approves. | `test_signup.py`. Live: sign-up and approval. |
| Passwords | Go only to Identity Platform (browser SDK or REST); the API never receives, stores or logs them. Admin-created teachers and the admin set theirs from a one-time link. | Code review; `test_signup.py` checks nothing password-like is stored. |
| Sign-in key | Limited to the two sign-in services, the app's address, and Google's hosted email-action page for this project. | Live: the key used from another site is refused (403). |
| No direct client access to Firestore | Deny-all rules; the API uses a service account. | Live: unauthenticated REST read → 403. |
| Photos | Private bucket with uniform access and public access prevention; only the API's service account has access, to that bucket only. Viewed only through 15-minute signed links: the teacher sees every page, a student only their own while the work is open. Metadata is stripped twice. | `test_writing.py`. Live: bucket listing → 401; a student's photo link works; after the student is deleted the link no longer does. |
| The AI service is private | Only the API's service account may call it. | Live: direct request → 403. |
| Students see only their own released work | Student views are built from models with no teacher-only fields; the error view counts released work only, and revision marks only once sent back. | `test_exercises.py`, `test_review.py`, `test_writing.py`, `test_profile.py`, `test_teacher_isolation.py`. Live: the student saw their spans and no corrections. |
| No student text in logs | Only id/count/type events are logged; unexpected errors log their type and path only. | `test_safe_logging.py`. |
| Prompt injection | Student text goes inside `<data>` blocks the prompt says are never instructions, with any data tags defanged; output is schema-forced and validated in the harness and again in the API. | `harness/tests/test_operations.py`. |
| Spend | Hard monthly cap checked before every AI call, added atomically; at most $20; 75% alert; Google budget alerts at $10/$15/$20. | `test_spending.py`, `test_harness_ops.py`. Live: the admin's spending showed the test's AI calls. |
| Deletion | Deleting a student removes photos, exercises, submissions, job records and the login; re-runnable. Backups expire within 7 days. | `test_delete_student.py`. Live. |
| Audit log | Student lifecycle, reopens, class and assignment changes, and every admin action. | Tests across the suite. |
| Backups | Daily, kept 7 days. | Created with the setup script. |

## Known limits (accepted, or for later)

- **AI provider while Claude isn't enabled:** every call goes to Gemini, which may keep prompts briefly for abuse monitoring. Prompts contain only scrubbed text and random ids, but handwriting photos go unscrubbed.
- **Scrubbing is manual.** A name the teacher misses reaches the AI provider. Photos are never scrubbed; students are asked to write only their first name.
- **Taken emails can be discovered.** Even with enumeration protection on, Identity Platform's sign-up API answers `EMAIL_EXISTS` for a registered email (verified live). The sign-up page shows a neutral message, but someone calling the API directly can tell. Student usernames are unique across the school, so a teacher can tell that a username exists.
- **The daily sign-up limit can be used up** by someone creating requests, blocking real sign-ups for that day (the admin is emailed for each, and can also create teachers directly).
- **Authenticator setup window.** Between approval (or an admin resetting a lost authenticator) and the teacher adding their app, the password alone reaches the setup screen, so someone with that password could add their own authenticator. New accounts must verify their email first, which narrows this.
- A signed photo link works for its full 15 minutes, even after sign-out.
- The cap can be overshot by a few cents when calls are already running, and the 75% alert can arrive twice.
- The audit log has no screen; read it in Firestore.
- Job records of failed AI calls keep the error message (which can quote scrubbed text); they're deleted with the student.
- The Content-Security-Policy allows inline style attributes (React sets bar widths that way); inline scripts are not allowed.
- Identity Platform created an unused broad browser key; Firestore's rules make it useless for data access.
- Not yet measured: the AI's accuracy on real teacher-marked passages (the golden set is still synthetic).
