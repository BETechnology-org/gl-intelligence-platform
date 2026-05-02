#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────────────
# BL/GL Intelligence — single-command deploy to Cloud Run
# Replaces the legacy Flask gl-intelligence service with the Next.js 16
# product (DISE + Tax + audit log + close tracker + exports).
#
# Prerequisites (one-time):
#   gcloud auth login
#   gcloud auth application-default login
#   gcloud config set project trufflesai-loans
#
# Repo-level prerequisites (one-time):
#   1. Artifact Registry repo `gl-intelligence` in us-central1.
#      gcloud artifacts repositories create gl-intelligence \
#        --repository-format=docker --location=us-central1
#   2. Two Secret Manager entries:
#        bl-intelligence-supabase-service-role  (Supabase → Settings → API → service_role)
#        bl-intelligence-anthropic-api-key      (console.anthropic.com)
#      gcloud secrets create bl-intelligence-supabase-service-role --replication-policy=automatic
#      printf '%s' "<SERVICE_ROLE_KEY>" | gcloud secrets versions add bl-intelligence-supabase-service-role --data-file=-
#      gcloud secrets create bl-intelligence-anthropic-api-key --replication-policy=automatic
#      printf '%s' "<ANTHROPIC_KEY>"   | gcloud secrets versions add bl-intelligence-anthropic-api-key --data-file=-
#   3. Cloud Run runtime SA must have `roles/secretmanager.secretAccessor` on those secrets:
#      RUNTIME_SA=$(gcloud run services describe gl-intelligence --region=us-central1 --format='value(spec.template.spec.serviceAccountName)' 2>/dev/null || echo "462410669395-compute@developer.gserviceaccount.com")
#      for s in bl-intelligence-supabase-service-role bl-intelligence-anthropic-api-key; do
#        gcloud secrets add-iam-policy-binding "$s" \
#          --member="serviceAccount:${RUNTIME_SA}" --role="roles/secretmanager.secretAccessor"
#      done
# ────────────────────────────────────────────────────────────────────────
set -euo pipefail

PROJECT="trufflesai-loans"
REGION="us-central1"
SERVICE="gl-intelligence"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

cd "$ROOT"

echo "▸ Submitting Cloud Build (${PROJECT})..."
gcloud builds submit \
  --project="${PROJECT}" \
  --config="cloudbuild.yaml" \
  .

URL="$(gcloud run services describe "${SERVICE}" \
  --region="${REGION}" --project="${PROJECT}" \
  --format='value(status.url)')"

echo
echo "✅ Deployed."
echo "   Service: ${SERVICE}"
echo "   URL:     ${URL}"
echo
echo "Smoke-test:"
echo "   curl -sI ${URL}/"
echo "   curl -sI ${URL}/login"
echo "   curl -sI ${URL}/dashboard   # → 307 to /login until you sign in"
