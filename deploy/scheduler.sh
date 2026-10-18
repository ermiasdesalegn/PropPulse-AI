#!/usr/bin/env bash
# Create/update the Cloud Scheduler job that runs the daily proactive workflow (07:00 local time).
# Usage: PROJECT_ID=my-project REGION=us-central1 ./deploy/scheduler.sh https://proppulse-api-xxxx.run.app
set -euo pipefail

BACKEND_URL="${1:?usage: scheduler.sh <backend-url>}"
PROJECT_ID="${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-us-central1}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CRON_SECRET="${CRON_SECRET:-$(grep -E '^CRON_SECRET=' "$ROOT/backend/.env" | cut -d= -f2-)}"
TIMEZONE="${TIMEZONE:-$(grep -E '^TIMEZONE=' "$ROOT/backend/.env" | cut -d= -f2- || echo Africa/Addis_Ababa)}"
JOB="proppulse-daily-proactive-run"

ARGS=(
  --project "$PROJECT_ID"
  --location "$REGION"
  --schedule "0 7 * * *"
  --time-zone "${TIMEZONE:-Africa/Addis_Ababa}"
  --uri "${BACKEND_URL%/}/api/cron/daily-proactive-run"
  --http-method POST
  --attempt-deadline 300s
)

if gcloud scheduler jobs describe "$JOB" --project "$PROJECT_ID" --location "$REGION" >/dev/null 2>&1; then
  gcloud scheduler jobs update http "$JOB" "${ARGS[@]}" --update-headers "X-Cron-Secret=$CRON_SECRET"
else
  gcloud scheduler jobs create http "$JOB" "${ARGS[@]}" --headers "X-Cron-Secret=$CRON_SECRET"
fi
echo "Scheduled $JOB daily at 07:00 ($TIMEZONE). Trigger now with:"
echo "  gcloud scheduler jobs run $JOB --project $PROJECT_ID --location $REGION"
