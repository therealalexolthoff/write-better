# Google Cloud setup and operations

Write Better runs on one Google Cloud project, `write-better-app` (region `us-east4`). Everything below is done with gcloud and REST calls; nothing needs the Cloud Console except requesting Claude access.

## Setting up a project from scratch

1. Install the [gcloud CLI](https://cloud.google.com/sdk/docs/install) and run `gcloud auth login` as a project owner. No local Docker: images build with Cloud Build.
2. Fill in `PROJECT_ID`, `BILLING_ACCOUNT_ID` and `REGION` at the top of `infra/setup_gcp.sh`, read it, and run it section by section. It creates:
   - Firestore (native mode) with daily backups kept 7 days, and the private photo bucket;
   - the two service accounts with only the roles they need (the API's storage access is limited to the photo bucket);
   - Identity Platform: email and password sign-in with sign-up allowed (teachers have no role until the admin approves them), authenticator apps (TOTP), email enumeration protection, and users can't delete themselves from the browser;
   - the browser's sign-in key, limited to the two sign-in services and to the app's address;
   - both Cloud Run services: the harness is private (only the API's service account may call it, at most 2 instances), the API is public (at most 3 instances);
   - the deny-all Firestore rules (`infra/firestore.rules`).
3. Then:
   - **Budget** (alerts to billing admins at $10, $15 and $20):
     `gcloud billing budgets create --billing-account=<id> --display-name="Write Better monthly" --budget-amount=20USD --filter-projects=projects/<project> --calendar-period=month --threshold-rule=percent=0.5 --threshold-rule=percent=0.75 --threshold-rule=percent=1.0`
   - **Alerts** to the admin (failed AI calls, server errors, AI spend, new teacher sign-ups): `ALERT_EMAIL=<email> ./infra/monitoring.sh`
   - **Admin account:** `GOOGLE_CLOUD_PROJECT=<project> .venv/bin/python infra/create_admin.py <admin email>`. It prints a one-time link to set the password; then sign in at `/sign-in`, verify the email and add an authenticator app.
   - **Claude access** (Cloud Console): Vertex AI > Model Garden > Claude Sonnet 5 > Enable, then IAM & Admin > Quotas: request the `anthropic-claude-sonnet` online prediction quota for the `us` multi-region. Access and quota are separate gates, with no fixed approval time. Until both are granted, every AI call falls back to Gemini (docs/HARNESS_SPEC.md section 8).

## Deploying a change

From the repo root, with tests passing:

```sh
P=write-better-app; R=us-east4; REPO=$R-docker.pkg.dev/$P/wb-images
gcloud builds submit --project $P --region $R --config infra/cloudbuild.yaml \
  --substitutions="_DOCKERFILE=api/Dockerfile,_IMAGE=$REPO/wb-api:latest" .
gcloud run deploy wb-api --project $P --region $R --image $REPO/wb-api:latest
```

The same for the harness (`harness/Dockerfile`, `wb-harness`). `gcloud run deploy` with only `--image` keeps the service's settings. The upload skips everything git ignores, including `CLAUDE.local.md`.

## Live tests (run after a deploy)

- `GOOGLE_CLOUD_PROJECT=write-better-app .venv/bin/python scripts/live_test.py <app URL> <a JPEG file>`: the whole path through the API with throwaway accounts and real authenticator codes, including two real AI calls (a few cents), a second teacher's isolation, resetting an authenticator, and deleting a student. 26 checks.
- `node scripts/browser_test.mjs <app URL>`: a teacher's sign-up, approval, authenticator setup and sign-in through the real pages in headless Chrome, under the live security headers. 9 checks.

Both delete everything they create, even when a check fails.

## Re-runnable hardening

- Firestore rules: `GOOGLE_CLOUD_PROJECT=<project> .venv/bin/python infra/deploy_firestore_rules.py`
- Alerts: `ALERT_EMAIL=<email> ./infra/monitoring.sh` (existing ones are left alone)
- After any prompt or model change: `.venv/bin/python scripts/golden_set.py` (real passages go in `golden/private/`, which git ignores)

## Notes

- After granting a Cloud Run invoker role, allow up to a minute before the API can call the harness: a 403 right after granting is propagation, not a mistake.
- Identity Platform also created a broad "Browser key (auto created by Firebase)". Write Better never uses or publishes it, and Firestore's deny-all rules make it useless for data access.
- Deleting resources the setup created isn't covered here; do it by hand and deliberately.

## write-better-app status (2026-11-09)

- App: https://wb-api-1046905375357.us-east4.run.app (no custom domain yet).
- Deployed and checked: both services, Firestore with backups, the photo bucket, Identity Platform, the restricted sign-in key, the deny-all rules, the $20 budget, and four alert policies to alex.olthoff@tuta.com. Both live tests pass.
- Claude: not enabled yet (calls return 429), so AI calls use Gemini.
- A custom domain later means adding it to Identity Platform's authorized domains and the sign-in key's allowed referrers.
