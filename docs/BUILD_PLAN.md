# Write Better: Build Plan

Status: planning, updated 2026-11-07. No code written yet. The app is called **Write Better** for now. Public pages don't name any school.

A free writing-review tool for a language school's teachers and adult students, built from the `therealalexolthoff/grammar-checker` repo. It keeps the existing review flow and replaces the single teacher with admin, teacher, class and student levels. It adds a public home page, a teacher sign-up request, a view of each student's own errors, and a full styling pass.

The core promise stays the same: the AI drafts, the teacher decides, and nothing reaches a student without teacher approval.

## Decisions

| Topic | Decision |
|---|---|
| Users | One language school. Free to use. All students are over 18. |
| Admin | The owner, for now. Admin approves teacher sign-ups and can also create teachers directly. |
| Sign-up | Public home page with a teacher sign-up form: name, email and password only. The account can't do anything until the admin approves it. Students never sign up: teachers create their accounts. |
| Teachers | Kept separate: a teacher sees only their own classes and students. |
| Student errors | Students see their own errors across all their returned work, as a chart with examples. |
| Design | Every page gets a consistent, polished design, including the home page, sign-in, sign-up and teacher setup. |
| Hosting | New repo and new Google Cloud project, under the owner's account. |
| Cost | The total stays under $20 a month, AI included. The owner manages usage, so there are no per-teacher limits. |
| Cut | Grammar exercises, short answers, AI-generated prompts, personalized lessons. |
| Kept | Writing assignments, typed and handwritten work, scrubbing, AI evaluation, teacher review, revision round, learner profiles, private teacher notes. |
| On hold | Resource library and weekly action plans for students. |
| Existing app | `grammar-checker` stays as it is. No data moves across. |

## Assumptions to confirm

These are defaults chosen for the plan. They have not been agreed yet.

1. A student belongs to one class at a time. Their learner profile follows them if they move.
2. Student usernames are unique across the school, for example `maria.k`.
3. Admin manages accounts and spending but cannot read student work or teacher notes.
4. A teacher can't be deleted while they still have classes. Admin transfers the classes first.
5. There is no email service of our own. Identity Platform's built-in emails handle email verification and password resets. Approval isn't emailed: a teacher who signs in before approval sees a "waiting for approval" page. Teachers the admin creates directly get a one-time setup link that the admin sends.
6. Teachers write their own assignment prompts, and can't edit one after it has been assigned.
7. The AI cap starts at $15 a month, which leaves room under $20. Admin can change it.
8. The Gemini fallback stays. It is only needed while Claude is unavailable.
9. Sign-ups that are rejected, or left pending for 30 days, are deleted along with their login.
10. No new frontend dependencies: pages, routing and charts use the existing React setup, plain CSS and SVG. Ask before adding a library.

## Not in this version

School level above teachers, per-teacher budgets, co-teachers, open sign-up without approval, student sign-up, notifications, student password change, numeric scores, automatic name scrubbing, resource library, weekly action plans.

## Phases

Each phase ends with the tests passing, CI green, and a stop for the owner's review. Follow the existing habit of marking commits `NOT YET TESTED LIVE` until a feature has been tried on the real deployment.

### Phase 0: Set up

- Create the new repo from a copy of `grammar-checker`, and confirm the existing tests pass before changing anything.
- Create the new Google Cloud project. Change `PROJECT_ID` and the service names in `infra/setup_gcp.sh`.
- Request Vertex AI access to Claude right away. Approval has no fixed timeline.
- Add a GitHub Actions workflow that runs the tests on every push. The current repo has none, and the isolation tests below only protect the app if they run automatically.
- Rewrite `CLAUDE.md` and `README.md` for Write Better, keeping the privacy rules. Mark the other docs as describing the single-teacher app.
- Each later phase updates the docs it changes: `REQUIREMENTS.md` and `HARNESS_SPEC.md` in Phase 1, `ARCHITECTURE.md` in Phase 2, `SECURITY_REVIEW.md` in Phase 8, and `infra/README.md` when the project is set up.

### Phase 1: Make the cuts

`exercises.py` can't simply be deleted. Writing is stored as a type of exercise, and `writing.py` and `review.py` import helpers from it (`call_ai`, `_load_exercise`, `_teacher_view`, `update_open_submission` and others).

Keep the internal `exercises` name for now and show "writing assignment" in the interface. Renaming it adds risk and gives users nothing.

**Remove from the API (`api/app/`):**
- `lessons.py`, `grading.py` and `context.py`. Only generation uses `context.py`.
- The generate, regenerate and draft-only routes in `exercises.py`.
- Grammar and short-answer paths in `exercises.py`, `review.py`, `models.py` and `profile.py`, including `wrong_item_codes`.
- Lesson references in `overview.py` and in the delete-student cascade.

**Remove from the AI service (`harness/`):** `generate_exercise`, `evaluate_exercise` and `generate_lesson`, with their prompts, mocks and schemas. That leaves two operations: `transcribe` and `evaluate_writing`.

**Remove from the frontend (`web/src/`):** `LessonBody`, `ReadLesson`, `LessonScreen`, `ShortAnswerReview`, the grammar parts of `DoExercise` and `ExerciseScreen`, and the Lessons tab.

**Privacy gain:** with generation gone, teacher notes are no longer sent to the AI provider. Remove the warning on the notes screen and update the docs.

**Done when:** the writing flow works from assignment through to revision, and the learner profile still works, with nothing above left in the code.

### Phase 2: Roles, ownership and teacher isolation

This is the most important phase. Today any teacher can see everything, and several routes read whole collections.

**Data changes** (Phase 2 adds `teacher_id` everywhere; the new collections are created in the phases that build them: `teachers` and `signup_requests` in Phase 4, `classes` in Phase 5, `assignments` in Phase 6):

| Collection | Change |
|---|---|
| `teachers` (new) | auth uid, display name, email, active, created_at |
| `signup_requests` (new) | auth uid, name, email, status, created_at |
| `classes` (new) | teacher_id, name, archived, created_at |
| `assignments` (new) | teacher_id, class_id, title, prompt, word limits, created_at |
| `students` | add teacher_id, class_id |
| `exercises` | add teacher_id, class_id, assignment_id |
| `submissions`, `jobs` | add teacher_id |

**Authorization:**
- Add the `admin` role to `auth.py`, and require the authenticator code for admins as well as teachers.
- Add one shared ownership check for students, classes, assignments and exercises. Replace `require_self_or_teacher` and every direct `require_teacher` lookup with it.
- Return "not found" for another teacher's records, so a teacher can't tell that they exist.
- Filter every list by teacher, including `list_students` and `class_overview`, which currently read everything.

**Tests that must exist:**
- Every route, called by teacher B against teacher A's records, is refused. Build this like `test_every_route_needs_login.py`, so a new route can't be missed.
- Every route that exposes student work is refused for admins.
- Students still see only their own released work.
- Signed-in users with no role (pending sign-ups) can reach only the sign-up status route.
- The sign-up request is the only route that accepts data without a full login. Add it to that test's `PUBLIC` list, and add a test that fails if any other public route appears.

**Done when:** those tests pass and no query returns data across teachers.

### Phase 3: Design system and public pages

Do this before the new screens in later phases, so they're built in the new style rather than restyled afterward.

The current app has 165 lines of plain CSS (`web/src/styles.css`) with sensible foundations: phone-first, large text and high contrast. It has no router. `App.tsx` shows either the sign-in screen or the app, so public pages need simple path-based routing.

**Design system** (in `styles.css`):
- Colour, type scale and spacing, built on the existing variables.
- Shared components: buttons, form fields, cards, tables, tabs, status labels for each pipeline stage, error-type colours that match the highlighted mistakes in student work, empty states, loading states and error messages.
- Phone-first for students; laptop-first for teachers and admin.
- Accessibility: WCAG AA contrast, large tap targets, visible keyboard focus, labelled fields, and plain-language error messages.

**Public pages:**
- **Privacy page:** a short, plain-language page linked from the home page and sign-up: who runs the tool, what goes to the AI provider, and how deletion works. Not a legal document.
- **Home page:** what the tool does, how it works in three steps (teacher assigns, student writes or photographs their work, teacher reviews AI-drafted feedback), a plain-language privacy summary, and buttons to sign in or sign up as a teacher. Static, with no student data.
- **Sign-in:** one page with separate student and staff options. Students use a username and password. Teachers and admin use email, password and an authenticator code. Explain what to do after a forgotten password: students ask their teacher, and teachers ask the admin.
- **Teacher sign-up:** name, email and password, then "check your email" and "waiting for approval" pages. See Phase 4.
- **Teacher setup:** a step-by-step flow after approval, or from a setup link: verify the email if needed, scan the authenticator QR code, enter a code, done.

**Existing screens:** restyle every teacher, student and review screen to the design system, especially the dense review screens (`WritingReview`, `ExerciseScreen`).

**Done when:** every page has been checked at phone and laptop widths, and the owner has approved screenshots of each.

**Status (2026-11-09):** colours are the school's (burgundy main colour, cyan accent; see `web/src/styles.css`). The sign-up form, the "check your email" and "waiting for approval" pages and the teacher setup flow are built in Phase 4, together with the logic behind them, using this design system: building them here would mean screens with nothing behind them. Screenshots come from a development-only preview (`web/preview.html`).

### Phase 4: Admin, sign-up and teacher accounts

**Sign-up requests:**
- The form takes name, email and password. Identity Platform creates the login and sends a verification email. The login has no role, so the API refuses it everywhere except the sign-up status route.
- Passwords go only to Identity Platform. They are never stored by the API or logged.
- Turn on Identity Platform's email enumeration protection, so the form doesn't reveal which emails are registered. [VERIFY] how this behaves at sign-up.
- Spam protection: a daily limit on new sign-ups, Identity Platform's built-in limits, and a hidden field that bots fill in. Ask before adding a CAPTCHA service.
- New sign-ups trigger an email alert to the admin through the existing monitoring setup.
- Admin screen lists pending sign-ups. Approve adds the teacher role. Reject deletes the login and the request.

**Accounts:**
- A one-time script creates the admin account, based on `infra/set_teacher_role.py`.
- Admin screen: create, deactivate, reactivate and reset teachers, and transfer a teacher's classes to another teacher.
- Transfers update every owned record and are safe to run again if they stop partway, like student deletion.
- `Login.tsx` only handles sign-in today, so sign-up, email verification and authenticator setup are new work.
- Record all admin actions in the audit log.

**Done when:** a teacher can go from sign-up to signed in without anyone using the Google Cloud console.

**Status (2026-11-09):** built and tested with fakes for Identity Platform: the sign-up, waiting, setup and admin screens, `api/app/signup.py`, `api/app/admin.py`, `infra/create_admin.py` and the sign-up alert. To check live once deployed: [VERIFY] that clearing a lost authenticator works (`identity.clear_authenticator`), how email enumeration protection affects sign-up, and the whole sign-up-to-signed-in path. The authenticator setup shows a QR code (`qrcode-generator`, added with the owner's approval on 2026-11-09), with the setup key and a phone link as a fallback.

### Phase 5: Classes, students and the student error view

**Classes and students:**
- Teachers create, rename and archive classes.
- `StudentsPanel` moves inside a class: create, deactivate, reset password, delete, and move between the teacher's classes.
- `Overview` becomes per class, with a view across all of a teacher's classes.
- A student's profile and notes stay with the student when they move.

**Student error view:**
- A new route returns the signed-in student's own error summary. It never includes teacher notes.
- **Only work already returned to the student counts.** The teacher's profile counts `ready_to_release`, which the student hasn't seen yet. The student view must count only `released` and the revision states after it, or students would see errors before their teacher releases the feedback.
- A chart of error types across all their returned work, most frequent first, using plain-language names rather than codes.
- A "recent work" view of the last few pieces next to "all work", so students can see whether a type of mistake is becoming less common.
- Tapping an error type shows real examples from their own writing, highlighted the same way as on their returned work, and whether their revisions fixed them.
- Counts appear as plain counts, such as "4 times", never as scores, percentages or grades.
- A friendly empty state before any work has been returned.
- Built with SVG and CSS, with no chart library. It needs no AI calls and adds no cost.

**Tests:** a student sees only their own data, nothing from before release, and no teacher notes.

**Status (2026-11-09):** built: `api/app/classes.py`, class filters on students and the overview, moving students, admin transfers that move classes too, and the error view (`api/app/progress.py`, `web/src/student/MyProgress.tsx`). Found while building: revision outcomes the teacher has marked but not yet sent would also have leaked into the student view; it leaves them out until sent, and a test checks it.

### Phase 6: Class writing assignments

- Build on `assign_writing_to_students`. Each student keeps their own copy, so the existing review flow doesn't change.
- A new `assignments` record links the copies, so a teacher can assign to a whole class or chosen students and see everyone's progress in one place.
- A student who joins a class later can be added to an existing assignment.

**Status (2026-11-09):** built: `api/app/assignments.py` (create for a whole class or chosen students, list with progress counts, one assignment's view, add students), replacing `POST /exercises/writing-for-students`; admin transfers move assignments too. Screens: "Assign writing" (class, whole class or chosen students), an Assignments tab and one view per assignment.

### Phase 7: Spending

- Change `spend.py` to an atomic increment. The current read-then-write relies on there being only one teacher.
- Show monthly spend and the cap setting on the admin screen.
- Send spending alerts to the admin, and add Google billing alerts at $10 and $15.
- When the cap is reached, teachers see a clear message that AI feedback is paused. They can still read and edit existing work.

**Status (2026-11-09):** built: atomic spend (`api/app/spend.py`), the admin's Spending tab and cap setting (`GET /admin/spending`, `PUT /admin/spending/cap`, capped at $20, default $15), `GET /ai-status` and the teacher's "paused" notice. The 75% alert already goes to the admin through `infra/monitoring.sh`, and the Google budget (alerts at $10, $15 and $20) was set up in Phase 0.

### Phase 8: Check and launch

- Redo `docs/SECURITY_REVIEW.md` for the new roles and the public sign-up route.
- Replace the placeholder accuracy passages with 8 to 10 real ones marked up by a teacher, and run `scripts/golden_set.py`. Keep them in `golden/private/`. Student work must never go in the repo.
- Tell students in plain language, in the app and on the home page, that their writing is reviewed with AI, and that photos of handwriting go to the AI service unscrubbed.
- Deploy and run a full live test with a test admin, two test teachers and test students. Include a check that the two teachers can't see each other's work.
- Pilot with one or two teachers before opening sign-up to the rest.

**Status (2026-11-09):** done except the golden set (postponed by the owner) and the pilot. Security review redone (`docs/SECURITY_REVIEW.md`): security headers added, a taken username no longer crashes, instance limits set. Deployed to write-better-app with `infra/setup_gcp.sh` (now fully scripted, Identity Platform included) and checked live: `scripts/live_test.py` (26 checks, including real AI through the Gemini fallback, a second teacher's isolation, resetting an authenticator, deleting a student) and `scripts/browser_test.mjs` (the real sign-up, setup, sign-in and email-link pages; 14 checks). Students are told on the writing screen that AI helps their teacher.

### Phase 9: Installable phone app (PWA)

Decided 2026-11-11: an installable web app ("Add to Home Screen") instead of app-store apps, for now. No store fees, no new dependencies, same code. A store wrapper (Capacitor) stays possible later.

- `web/public/manifest.json`: name, icons, opens at `/app` full-screen.
- `web/public/icons/`: phone icons rendered from `app-icon.svg`.
- `web/public/sw.js`: service worker that only stores the offline page and its icon. It never caches pages, API responses, writing or photos.
- `web/public/offline.html`: shown when a page can't load.

**Status (2026-11-11):** done and checked locally in Chrome (installable, no manifest errors, offline page shown when the server is down). NOT YET TESTED LIVE: install on a real iPhone and Android phone after the next deploy. Push notifications are not included; they would need a new dependency and stored subscriptions.

## Main risks

- **A missed ownership check** would expose another teacher's students. The Phase 2 tests are the protection.
- **The public sign-up form** is the only part of the app open to anyone. A new login has no access until the admin approves it, but the form can still receive spam.
- **Manual scrubbing** may feel slow for busy teachers, and a missed name reaches the AI provider. Watch this during the pilot. Highlighting names from the class list is the obvious next step.
- **The AI cap** pauses feedback for every teacher at once when it's reached.
- **Vertex AI approval** could delay the launch, so request it in Phase 0.
