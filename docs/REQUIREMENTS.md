# Requirements (v1)

> **Status:** updated in Phase 1 (2026-11-09): Write Better reviews writing only. Grammar exercises, short answers, AI-generated exercises and lessons are cut; their requirement numbers are kept, marked "Removed", because the code refers to requirements by number. Accounts and access (4.1) were updated in Phase 4. Where this and `docs/BUILD_PLAN.md` disagree, the build plan wins.

Items marked **[VERIFY]** must be confirmed by the coding agent before relying on them.

## 1. Purpose and context
A free web app that helps adult language learners write better English. The teacher writes a writing exercise and assigns it; students write on their phones or on paper; an AI "harness" (Claude) drafts feedback on grammar, punctuation, spelling and capitalization; the teacher reviews, edits and releases it; and the app keeps a per-student learner profile of approved errors.

Users:
- **Teacher**: exactly one, ever. Laptop-first UI.
- **Students**: adults, advanced level, English-only UI, phone-first UI. Identified only by an agreed pseudonym ("American name"), never real names.

## 2. Scope of v1
In scope: grammar and punctuation errors in students' writing, including spelling and capitalization. Out of scope for v1: grammar exercises, AI-written exercises or lessons, cohesion, structure, style, word choice, scores of any kind, notifications, retakes, native/PWA apps, multiple languages, student password change. (Multiple teachers, classes and a public sign-up come in later phases: see the build plan.)

## 3. Glossary
- **Harness**: separate backend service that calls Claude via Vertex AI. Has no database access.
- **Writing exercise**: one prompt written by the teacher, a free-form response, evaluated with coded annotations, never marked or scored.
- **Scrubbed text**: a teacher-edited copy of student text with personal data removed. The only student text ever sent to the harness (exception: handwriting photos for transcription).
- **Annotation**: a coded error span (see the 14-code taxonomy in HARNESS_SPEC.md).

## 4. Functional requirements

### 4.1 Accounts and access
- FR-0. Each teacher organizes their students into classes: create, rename, archive (keeps the students and their work, takes no new students) and reopen. Every student belongs to one of their teacher's classes and can be moved to another of them; their work, profile and notes go with them. The teacher's screens can show one class or all of them.
- FR-1. Only a teacher creates their students' accounts: username (for example `maria.k`, unique across the school) plus a teacher-set password. No email, no student self-signup. Students cannot change their own password; only their teacher resets it.
- FR-1a. Teachers sign up on the public sign-up page (name, email, password) or are created by the admin. A sign-up has no role and reaches nothing but its own request until the admin approves it; rejecting deletes the login. Requests pending more than 30 days are deleted. Spam protection: a hidden form field, a daily limit of 20 new requests, and Identity Platform's own limits. The admin gets an email alert for each new sign-up.
- FR-2. Teachers and the admin use email + password + TOTP MFA (any RFC 6238 authenticator app, e.g. Google Authenticator, Authy). On first sign-in the app walks them through verifying their email and adding the authenticator app; the API refuses their tokens until they sign in with a code. **Confirmed:** Identity Platform requires the email be verified before TOTP enrollment. Students never enroll in MFA.
- FR-3. Students can access only their own released content. A teacher can view and manage only their own students' data, and cannot log in as a student. The admin manages accounts and never sees student work.
- FR-3a. The admin can approve or reject sign-ups; create a teacher (with a one-time link to set their password); deactivate and reactivate a teacher; get a new password link; reset a lost authenticator app; and transfer all of a teacher's students and their work to another teacher. There is no email service of our own: the admin sends links themselves. All admin actions are audit-logged.
- FR-4. A teacher can deactivate one of their students, and delete one with all their data (including photos). Deletion requires typing the username to confirm and explains that backups expire within 7 days.
- FR-5. Overrides, reopens, deletions, and password resets are recorded in an audit log. **Extended (teacher decision):** student account creation and deactivation are audit-logged too, for the same reason - they're account-lifecycle actions in the same risk category.

### 4.2 Writing exercises (teacher)
- FR-6 and FR-7. Removed: the AI no longer generates exercises.
- FR-8. Every AI result is validated against its schema (HARNESS_SPEC.md); invalid output is never shown to the teacher.
- FR-9. Removed: there are no drafts to edit or regenerate.
- FR-10. Every exercise copy belongs to exactly one student. No due dates. The teacher tells students in class; the student sees an "assigned to me" list.
- FR-11. Removed (grammar answer keys).
- FR-12. The teacher writes each writing assignment: title, prompt, optional min/max word counts. The AI never writes exercises. The teacher assigns it to one of their open classes, either the whole class (its active students) or chosen students in it; each gets their own copy (so FR-10 holds), which then follows the normal flow. One screen per assignment shows every student's stage (counted as not started, writing, needs you, correcting, done), opens any copy, and gives the assignment to students of the class who don't have it yet (for example, who joined later). Prompts are never changed after assigning. A typed response is always available to the student; photos of handwritten work can be added too (see 4.5). Word limits are advisory: the student sees a live word count and a gentle reminder when outside the limits, but can still submit.

### 4.3 Doing an exercise (student, phone-first)
- FR-13. Student sees assigned work and opens it. Answers autosave (debounced) and resume after app switching or signal loss.
- FR-14. Large tap targets and plain-English instructions. (Tap-to-place word ordering was removed with grammar exercises.)
- FR-15. Student presses Submit with a confirmation step. After submitting, no edits. No retakes. Only the teacher can reopen a submission (audit-logged), returning it to in-progress.

### 4.4 Grading, scrubbing, evaluation, release
- FR-16. Students see nothing until release. (Automatic grading of grammar items was removed.)
- FR-17. Removed.
- FR-18. After submit, the teacher opens a laptop review screen showing the original text and an editable scrubbed copy. The original is never modified or sent anywhere. Editing the scrubbed text after evaluation invalidates the draft evaluation and requires re-running it.
- FR-19. "Send for evaluation" sends only the scrubbed text and the prompt. The harness returns annotations and one overall comment.
- FR-20. Teacher can accept or edit every annotation (add, remove, recode) and the comment, and can regenerate with an optional note. All output is a draft until released.
- FR-21. Teacher releases results. The student sees their text with coded spans highlighted (code only; corrections and explanations stay teacher-only), plus the overall comment. No numeric score or percentage.
- FR-22. Students see their history of released work.

### 4.5 Handwritten writing responses
- FR-23. The teacher can upload multiple photos in page order for a student's exercise. EXIF/metadata is stripped. **Teacher decisions (2026-10-08):** photos can be uploaded any time before evaluation, whether or not the student typed anything; starting transcription locks the student's typed answer as if submitted. The teacher's browser re-draws each photo as a JPEG (at most 2000 px on the long side; this drops metadata and fixes rotation), and the API strips any remaining metadata segments again before storing - no image library needed. **Teacher decisions (2026-10-14):** the student can also take or choose photos of their own pages on an open writing exercise (same JPEG re-draw and metadata stripping). They see only their own pages, and only until they submit; they can remove their pages and start again. Submitting locks the photos with the typed answer. The teacher still starts transcription.
- FR-24. The harness transcribes photos verbatim (no correction, `[?]` for illegible words). Teacher sees a side-by-side screen (photos left, editable text right) and corrects the transcription. One response per exercise: the teacher designates which source (typed or transcription) is final.
- FR-25. The transcription then goes through the same scrub, evaluation, and release flow. Photos are visible to the teacher, retained until the student is deleted, and are never shown to students - except a student's own pages, to that student, until they submit (FR-23). Students are told to write only their agreed first name on handwritten work.

### 4.6 Revision
- FR-26. After release, the student sees their text with coded spans and can tap a flagged span to edit only that span. One round; submit locks it.
- FR-27. Originals, annotations, and revisions are stored separately. The teacher reads revisions side by side with changed spans highlighted and marks each attempted span `fixed`, `unfixed`, or `changed_wrongly`. **Teacher decision (2026-10-08):** only spans the student actually changed get an outcome; untouched spans get none. The student sees and revises the scrubbed (evaluated) text. Revisions are not sent to the harness in v1. **Teacher decision (2026-10-22):** once every changed span is marked, the teacher sends the outcomes to the student (`revision_reviewed`, shown to the student as "Corrections checked"); the marks are locked after sending. The student sees each changed span's outcome and, for spans not fixed, the suggested correction (an exception to FR-21; explanations stay hidden).

### 4.7 Writing lessons
- FR-28 and FR-29. Removed: no AI-generated lessons.

### 4.8 Learner profile
- FR-30. Per student, computed by plain code (never by the harness), from teacher-approved data only: counts per error code from approved annotations, plus revision outcomes per code, within a recency window (default last 5 submissions, configurable in settings).
- FR-30a. The student sees their own errors ("My progress"): a bar chart of error types, most frequent first, across all their returned work or their most recent pieces (the profile window), with up to 3 examples of each from their own writing and how their corrections went. Built from released work only, and revision outcomes only once the teacher has sent them back: never approved-but-unreleased work, marks not yet sent, teacher notes, corrections or explanations. Plain counts ("4 times"), never scores or percentages.
- FR-31. Teacher can view the profile and keep private free-text notes per student. Notes are never sent to the harness and never shown to the student.

### 4.9 Class overview (teacher)
- FR-32. One screen listing each student with pending work and pipeline stage (assigned, in progress, submitted, awaiting transcription review, awaiting scrub, evaluating, draft ready, ready to release, released, revision open, revision submitted, revision checked).

### 4.10 Operations
- FR-33. The app logs each harness call's tokens and cost, shows monthly spend, and enforces a hard monthly cap in the app (estimate before call, record after). At the cap, evaluation and transcription pause with a clear message. Cap is a setting.
- FR-34. Harness failures or timeouts leave the job in a retryable error state; no work is lost.
- FR-35. Student-facing UI is English only, plain language, large text, no jargon in errors.
- FR-36. No in-app AI-use notice is required; the teacher informs students in class that their work is processed by an AI provider.

## 5. Non-functional requirements
- **Platform**: Google Cloud only. **Confirmed:** `us-east4`/`us-east5` do not support current Claude models as fixed regional endpoints on Vertex; use the **`us` multi-region endpoint** instead (keeps data in the US; 10% price premium over the `global` endpoint, which has no US-residency guarantee). Single production project, no staging.
- **Budget**: total under $20/month including cloud and Claude. App-enforced Claude cap; billing alerts at $10 and $15 as backstop. **Confirmed estimate:** ~$1-4/month at 8 students, ~$5-15/month at 30 students (Claude spend; GCP infra stays within free tiers at this scale) — see ARCHITECTURE.md section 11.
- **Privacy**: students identified only by pseudonym and opaque ID; usernames never leave the API; harness gets scrubbed text only (photo-to-transcribe is the one exception); **confirmed:** Google/Anthropic do not train models on Vertex customer data; logs never contain student text or images.
- **Security**: no direct client access to the database or storage; all authorization in the API; photos only via short-lived signed URLs to the teacher; strict output validation of all harness results; student text treated as untrusted data in prompts.
- **Reliability**: single-teacher classroom use; no HA requirement. Daily Firestore backups with 7-day retention.
- **Usability**: mobile-first student UI, laptop-first teacher UI, accessible contrast and text size.

## 6. Open items (decide during build)
1. ~~Exact Claude model names per operation and Vertex region availability~~ **Resolved:** `claude-sonnet-5` for both harness operations, via the `us` multi-region Vertex endpoint. Upgrade `evaluate_writing`/`transcribe` to `claude-opus-5` only if golden-set results (HARNESS_SPEC.md section 9) show Sonnet missing or miscoding errors.
2. Teacher-provided golden set of 8 to 10 annotated passages (see HARNESS_SPEC.md section 9) before the first real student session.
3. Whether to add a "word choice" code later (deliberately excluded now).
4. Vertex AI Model Garden access for Claude models must be requested per-model before Phase 1 GCP setup; approval has no fixed SLA (seen stuck pending in 2026 reports) — request early so it isn't a blocker. **Confirmed 2026-10-08: access and serving quota are separate gates** — granting Model Garden access does not itself grant a nonzero per-minute request quota, and there is no self-service way to raise it (`gcloud alpha services quota update` caps the override at 0 for this metric). A real quota-increase request via Console is required too — see infra/README.md.
