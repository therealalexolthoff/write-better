#!/usr/bin/env bash
# One-time GCP project setup for Write Better.
#
# You run this yourself, step by step - it is not run automatically by
# anything, and nobody with access to this repo has run it for you. Most
# commands are idempotent (safe to re-run), but read each section before
# running it; a couple create billing-relevant resources.
#
# Prerequisites: gcloud CLI installed, `gcloud auth login` done, and a
# billing account you can link (`gcloud billing accounts list`). No local
# Docker needed - images are built remotely via Cloud Build
# (infra/cloudbuild.yaml).
#
# See infra/README.md for the full order of operations, including the
# console-only steps this script cannot do.

set -euo pipefail

# ---- fill these in before running ----
PROJECT_ID="write-better-app"
BILLING_ACCOUNT_ID="<billing account id>"
REGION="us-east4"                 # Cloud Run / Firestore / Storage region (US East, per docs/ARCHITECTURE.md)
# Identity Platform's browser API key (Console: Identity Platform > Application
# setup details > apiKey). Public by design - every browser that loads the
# app receives it - but not committed here.
FIREBASE_API_KEY="${FIREBASE_API_KEY:?set FIREBASE_API_KEY in the environment before running}"
# ---------------------------------------

BUCKET_NAME="${PROJECT_ID}-photos"
API_SA="wb-api-sa@${PROJECT_ID}.iam.gserviceaccount.com"
HARNESS_SA="wb-harness-sa@${PROJECT_ID}.iam.gserviceaccount.com"
ARTIFACT_REPO="${REGION}-docker.pkg.dev/${PROJECT_ID}/wb-images"

echo "== Project =="
# Skipped when the project already exists (write-better-app was created and
# linked to billing on 2026-11-09, with a $20 budget alerting at 50/75/100%).
if ! gcloud projects describe "${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud projects create "${PROJECT_ID}" --name="Write Better"
  gcloud billing projects link "${PROJECT_ID}" --billing-account="${BILLING_ACCOUNT_ID}"
fi
gcloud config set project "${PROJECT_ID}"

echo "== APIs =="
gcloud services enable \
  run.googleapis.com \
  firestore.googleapis.com \
  storage.googleapis.com \
  identitytoolkit.googleapis.com \
  aiplatform.googleapis.com \
  iamcredentials.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com

echo "== Firestore (native mode) =="
gcloud firestore databases create --location="${REGION}" --type=firestore-native

echo "== Firestore daily backups, 7-day retention (docs/ARCHITECTURE.md section 9) =="
gcloud firestore backups schedules create \
  --database='(default)' \
  --recurrence=daily \
  --retention=7d

echo "== Private photo bucket =="
gcloud storage buckets create "gs://${BUCKET_NAME}" \
  --location="${REGION}" \
  --uniform-bucket-level-access \
  --public-access-prevention

echo "== Service accounts =="
gcloud iam service-accounts create wb-api-sa --display-name="Write Better API service account"
gcloud iam service-accounts create wb-harness-sa --display-name="Write Better harness service account"

echo "== API service account roles =="
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${API_SA}" --role="roles/datastore.user"
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${API_SA}" --role="roles/storage.objectAdmin"
# Needed for firebase_admin.auth (create/update/delete student users) - api/app/identity.py.
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${API_SA}" --role="roles/firebaseauth.admin"
# Self-impersonation, needed only to sign Cloud Storage URLs - docs/ARCHITECTURE.md section 10.
gcloud iam service-accounts add-iam-policy-binding "${API_SA}" \
  --member="serviceAccount:${API_SA}" --role="roles/iam.serviceAccountTokenCreator"

echo "== Harness service account roles =="
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${HARNESS_SA}" --role="roles/aiplatform.user"

echo "== Container registry =="
gcloud artifacts repositories create wb-images \
  --repository-format=docker \
  --location="${REGION}"

echo "== Build and deploy the harness (private - no public access) =="
gcloud builds submit --config=infra/cloudbuild.yaml \
  --substitutions="_DOCKERFILE=harness/Dockerfile,_IMAGE=${ARTIFACT_REPO}/wb-harness:latest" .
gcloud run deploy wb-harness \
  --image="${ARTIFACT_REPO}/wb-harness:latest" \
  --region="${REGION}" \
  --service-account="${HARNESS_SA}" \
  --no-allow-unauthenticated \
  --set-env-vars="VERTEX_PROJECT_ID=${PROJECT_ID},VERTEX_REGION=us,HARNESS_MOCK_MODE=false"

HARNESS_URL="$(gcloud run services describe wb-harness --region="${REGION}" --format='value(status.url)')"

echo "== Build and deploy the API (public - the only thing anyone talks to) =="
gcloud builds submit --config=infra/cloudbuild.yaml \
  --substitutions="_DOCKERFILE=api/Dockerfile,_IMAGE=${ARTIFACT_REPO}/wb-api:latest" .
gcloud run deploy wb-api \
  --image="${ARTIFACT_REPO}/wb-api:latest" \
  --region="${REGION}" \
  --service-account="${API_SA}" \
  --allow-unauthenticated \
  --set-env-vars="HARNESS_URL=${HARNESS_URL},ENVIRONMENT=prod,FIREBASE_API_KEY=${FIREBASE_API_KEY},FIREBASE_AUTH_DOMAIN=${PROJECT_ID}.firebaseapp.com,PHOTO_BUCKET=${BUCKET_NAME}"

echo "== Let the API invoke the harness privately =="
gcloud run services add-iam-policy-binding wb-harness \
  --region="${REGION}" \
  --member="serviceAccount:${API_SA}" \
  --role="roles/run.invoker"

echo "== Verify: Phase 1 'done when' check =="
API_URL="$(gcloud run services describe wb-api --region="${REGION}" --format='value(status.url)')"
curl -sf "${API_URL}/health" && echo " <- API health OK"
curl -sf "${API_URL}/health/harness" && echo " <- API reached the harness privately: OK"

echo
echo "Done with what gcloud can do. Still manual - see infra/README.md:"
echo "  1. Request Vertex AI Model Garden access for the Claude model."
echo "  2. Enable Identity Platform + Email/Password provider + TOTP MFA (console only)."
echo "  3. Set billing alerts at \$10 and \$15 (console only)."
echo "  4. Give the teacher account its role: python infra/set_teacher_role.py <teacher email>"
