# GCP project setup

> **Status:** this document still describes the single-teacher app that Write Better was copied from. It is updated in the build phase that changes what it covers (see `docs/BUILD_PLAN.md`). Where they disagree, the build plan wins.

One-time setup for a fresh GCP project. Run in this order.

## 1. Before running the script

- Install the [gcloud CLI](https://cloud.google.com/sdk/docs/install). No local Docker needed - images build remotely via Cloud Build (`infra/cloudbuild.yaml`).
- `gcloud auth login`
- Pick a globally-unique project ID and find your billing account ID: `gcloud billing accounts list`
- Open `setup_gcp.sh` and fill in `PROJECT_ID`, `BILLING_ACCOUNT_ID`, and `REGION` at the top.
- `export FIREBASE_API_KEY=...` - Identity Platform's browser API key (Console: Identity Platform > Application setup details). The login screen needs it; the API hands it out from `GET /config`.

## 2. Run the script

```
./infra/setup_gcp.sh
```

It creates the project, enables the required APIs, creates Firestore (native mode, with a 7-day daily backup schedule), a private Cloud Storage bucket, the two service accounts with the roles they need, builds and deploys both Cloud Run services, and wires the API to invoke the harness privately. It ends by curling the API's `/health` and `/health/harness` endpoints to confirm Phase 1's "done when" criteria.

**Do this first, in parallel with everything else** - it has no fixed approval time and can block later work if left until last:

- Request Vertex AI Model Garden access for the Claude model (Console: Vertex AI > Model Garden > find the Claude model > Request access). Seen stuck pending for an unpredictable time in 2026 reports.
- **Model Garden access and serving quota are two separate gates.** Even after access is granted, the actual per-minute request quota for the base model can still be 0, which fails real calls with `429 RESOURCE_EXHAUSTED` (confirmed 2026-10-08 against this project). There is no self-service bump - `gcloud alpha services quota update` caps the consumer override at 0 for this metric. Request the real increase via Console: IAM & Admin > Quotas & System Limits > filter by service "Vertex AI API", search "claude" or "anthropic" > select the `anthropic-claude-sonnet` row (`us_multi_region_online_prediction_requests_per_base_model`) > Edit Quotas > submit with a justification. No fixed SLA observed - start this immediately, same as the access request.

## 3. Manual steps (console only - no gcloud command covers these)

- **Identity Platform**: Console > Identity Platform > Get Started. Enable the Email/Password provider. Enable TOTP MFA (Settings > Multi-factor authentication). The teacher's account needs a verified email before they can enroll in MFA (see docs/REQUIREMENTS.md FR-2).
- **Teacher role**: the API refuses tokens without a role claim. After creating the teacher account and enrolling TOTP, run `GOOGLE_CLOUD_PROJECT=<project id> python infra/set_teacher_role.py <teacher email>` (prints the account's current state; only writes if the role is missing).
- **Billing alerts**: done for `write-better-app` (see status below). For a new project: Console > Billing > Budgets & alerts, alerts at $10 and $15. These are a backstop behind the app's own spend cap, not the primary control.

## 4. Hardening (Phase 8) - re-runnable

- **Firestore rules** (deny all client access): `GOOGLE_CLOUD_PROJECT=<project id> .venv/bin/python infra/deploy_firestore_rules.py`
- **Alerts** emailed to the teacher (failed AI calls, server errors, spend): `ALERT_EMAIL=<email> ./infra/monitoring.sh`
- **Golden set** after any prompt or model change: `.venv/bin/python scripts/golden_set.py [set.json]` (the real set lives in `golden/private/`, git-ignored)

See docs/SECURITY_REVIEW.md for what these protect and how it was checked.

## Notes

- `setup_gcp.sh` is idempotent for most steps (safe to re-run), but re-creating the project or billing link will fail loudly if they already exist - that's expected, just skip ahead.
- Deleting resources this script created is not covered here; do that by hand and deliberately.
- After granting a Cloud Run IAM invoker binding, allow up to ~60 seconds for it to propagate before the private-invoke health check succeeds - a 403 right after granting the role isn't a misconfiguration, just propagation lag.

## Write Better project status

Project `write-better-app` (number 1046905375357), region `us-east4`, created 2026-11-09 in the owner's Google Cloud organization.

Done:
- Project created and linked to billing.
- Budget "Write Better monthly": $20 a month, scoped to this project, alerting billing admins at 50%, 75% and 100% ($10, $15, $20).
- APIs enabled: Vertex AI, Cloud Billing Budget.

Outstanding:
- Enable Claude in Vertex AI Model Garden for this project, then request serving quota (section 2). On the previous project the quota for `anthropic-claude-sonnet` started at 0 and had to be requested; expect the same here.
- Everything else in `setup_gcp.sh` (other APIs, Firestore, bucket, service accounts, deploy) and the manual Identity Platform steps. These run when the app is first deployed, not in Phase 0.
- Until Claude quota is granted, develop with the harness in mock mode; when deployed, calls fall back to Gemini 3.8 Flash.
