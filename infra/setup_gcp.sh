#!/usr/bin/env bash
# One-time Google Cloud setup for Write Better: everything the app runs on,
# including Identity Platform, all through gcloud and REST - no console.
# This is what set up write-better-app on 2026-11-09.
#
# You run this yourself, section by section - nothing runs it for you. Most
# commands are safe to re-run (they fail harmlessly if the thing exists),
# but read each section first: several create billable resources.
#
# Prerequisites: gcloud CLI, `gcloud auth login` as a project owner, and a
# billing account (`gcloud billing accounts list`). No local Docker: images
# build remotely with Cloud Build (infra/cloudbuild.yaml).
#
# Afterwards: infra/README.md (Claude access, the admin account, deploying
# changes, the live tests).

set -euo pipefail

# ---- fill these in before running ----
PROJECT_ID="write-better-app"
BILLING_ACCOUNT_ID="<billing account id>"
REGION="us-east4"                 # Cloud Run / Firestore / Storage region (US East, per docs/ARCHITECTURE.md)
# ---------------------------------------

BUCKET_NAME="${PROJECT_ID}-photos"
API_SA="wb-api-sa@${PROJECT_ID}.iam.gserviceaccount.com"
HARNESS_SA="wb-harness-sa@${PROJECT_ID}.iam.gserviceaccount.com"
ARTIFACT_REPO="${REGION}-docker.pkg.dev/${PROJECT_ID}/wb-images"
IDT="https://identitytoolkit.googleapis.com"

echo "== Project =="
if ! gcloud projects describe "${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud projects create "${PROJECT_ID}" --name="Write Better"
  gcloud billing projects link "${PROJECT_ID}" --billing-account="${BILLING_ACCOUNT_ID}"
fi
gcloud config set project "${PROJECT_ID}"
PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"

echo "== APIs =="
gcloud services enable \
  run.googleapis.com firestore.googleapis.com storage.googleapis.com identitytoolkit.googleapis.com \
  aiplatform.googleapis.com iamcredentials.googleapis.com artifactregistry.googleapis.com \
  cloudbuild.googleapis.com apikeys.googleapis.com firebaserules.googleapis.com \
  monitoring.googleapis.com logging.googleapis.com billingbudgets.googleapis.com

echo "== Firestore (native mode), daily backups kept 7 days (docs/ARCHITECTURE.md section 9) =="
gcloud firestore databases create --location="${REGION}" --type=firestore-native
gcloud firestore backups schedules create --database='(default)' --recurrence=daily --retention=7d

echo "== Private photo bucket =="
gcloud storage buckets create "gs://${BUCKET_NAME}" \
  --location="${REGION}" --uniform-bucket-level-access --public-access-prevention

echo "== Service accounts and their roles (only what each needs) =="
gcloud iam service-accounts create wb-api-sa --display-name="Write Better API service account"
gcloud iam service-accounts create wb-harness-sa --display-name="Write Better harness service account"
gcloud projects add-iam-policy-binding "${PROJECT_ID}" --member="serviceAccount:${API_SA}" --role="roles/datastore.user" --condition=None
# Accounts and roles in Identity Platform - api/app/identity.py.
gcloud projects add-iam-policy-binding "${PROJECT_ID}" --member="serviceAccount:${API_SA}" --role="roles/firebaseauth.admin" --condition=None
# Photos: the photo bucket only, not every bucket in the project.
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" --member="serviceAccount:${API_SA}" --role="roles/storage.objectAdmin"
# Self-impersonation, needed only to sign photo links - docs/ARCHITECTURE.md section 10.
gcloud iam service-accounts add-iam-policy-binding "${API_SA}" --member="serviceAccount:${API_SA}" --role="roles/iam.serviceAccountTokenCreator"
gcloud projects add-iam-policy-binding "${PROJECT_ID}" --member="serviceAccount:${HARNESS_SA}" --role="roles/aiplatform.user" --condition=None
# Cloud Build runs as the default compute service account in new projects.
for role in roles/logging.logWriter roles/artifactregistry.writer roles/storage.objectViewer; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" --role="${role}" --condition=None
done

echo "== Container registry =="
gcloud artifacts repositories create wb-images --repository-format=docker --location="${REGION}"

echo "== Identity Platform: email + password, sign-up allowed, authenticator apps, enumeration protection =="
idt() { curl -sf -X "$1" -H "Authorization: Bearer $(gcloud auth print-access-token)" -H "x-goog-user-project: ${PROJECT_ID}" \
  -H "Content-Type: application/json" "${IDT}$2" -d "$3" >/dev/null; }
idt POST "/v2/projects/${PROJECT_ID}/identityPlatform:initializeAuth" '{}'
idt PATCH "/admin/v2/projects/${PROJECT_ID}/config?updateMask=signIn.email,mfa,emailPrivacyConfig,client.permissions" '{
  "signIn": {"email": {"enabled": true, "passwordRequired": true}},
  "mfa": {"state": "ENABLED", "providerConfigs": [{"state": "ENABLED", "totpProviderConfig": {"adjacentIntervals": 5}}]},
  "emailPrivacyConfig": {"enableImprovedEmailPrivacy": true},
  "client": {"permissions": {"disabledUserSignup": false, "disabledUserDeletion": true}}}'

echo "== The browser's sign-in key: the two sign-in services only (restricted to the app's address below) =="
KEY_NAME="$(gcloud services api-keys create --display-name="Write Better browser sign-in" \
  --api-target=service=identitytoolkit.googleapis.com --api-target=service=securetoken.googleapis.com \
  --format='value(response.name)')"
FIREBASE_API_KEY="$(gcloud services api-keys get-key-string "${KEY_NAME##*/}" --format='value(keyString)')"

echo "== Build and deploy the harness (private: only the API may call it) =="
gcloud builds submit --region="${REGION}" --config=infra/cloudbuild.yaml \
  --substitutions="_DOCKERFILE=harness/Dockerfile,_IMAGE=${ARTIFACT_REPO}/wb-harness:latest" .
gcloud run deploy wb-harness --image="${ARTIFACT_REPO}/wb-harness:latest" --region="${REGION}" \
  --service-account="${HARNESS_SA}" --no-allow-unauthenticated --max-instances=2 --timeout=300 \
  --set-env-vars="VERTEX_PROJECT_ID=${PROJECT_ID},VERTEX_REGION=us,HARNESS_MOCK_MODE=false"
HARNESS_URL="$(gcloud run services describe wb-harness --region="${REGION}" --format='value(status.url)')"

echo "== Build and deploy the API (public: the only thing anyone talks to; it serves the app too) =="
gcloud builds submit --region="${REGION}" --config=infra/cloudbuild.yaml \
  --substitutions="_DOCKERFILE=api/Dockerfile,_IMAGE=${ARTIFACT_REPO}/wb-api:latest" .
gcloud run deploy wb-api --image="${ARTIFACT_REPO}/wb-api:latest" --region="${REGION}" \
  --service-account="${API_SA}" --allow-unauthenticated --max-instances=3 --timeout=300 \
  --set-env-vars="HARNESS_URL=${HARNESS_URL},ENVIRONMENT=prod,FIREBASE_API_KEY=${FIREBASE_API_KEY},FIREBASE_AUTH_DOMAIN=${PROJECT_ID}.firebaseapp.com,PHOTO_BUCKET=${BUCKET_NAME}"
gcloud run services add-iam-policy-binding wb-harness --region="${REGION}" --member="serviceAccount:${API_SA}" --role="roles/run.invoker"
API_URL="$(gcloud run services describe wb-api --region="${REGION}" --format='value(status.url)')"
APP_HOST="${API_URL#https://}"

echo "== Lock sign-in to the app's address =="
idt PATCH "/admin/v2/projects/${PROJECT_ID}/config?updateMask=authorizedDomains" \
  "{\"authorizedDomains\": [\"${PROJECT_ID}.firebaseapp.com\", \"${APP_HOST}\"]}"
gcloud services api-keys update "${KEY_NAME##*/}" --allowed-referrers="https://${APP_HOST}/*"

echo "== Deny all browser access to Firestore =="
GOOGLE_CLOUD_PROJECT="${PROJECT_ID}" python3 infra/deploy_firestore_rules.py

echo "== Check =="
curl -sf "${API_URL}/health" && echo " <- API OK"
curl -sf "${API_URL}/health/harness" && echo " <- the API reached the private harness"
echo
echo "App: ${API_URL}"
echo "Next (infra/README.md): billing budget, alerts (infra/monitoring.sh), the admin account"
echo "(infra/create_admin.py), Claude access in Model Garden, and the live tests."
