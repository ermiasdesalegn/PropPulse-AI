#!/usr/bin/env bash
# Deploy the FastAPI backend to Cloud Run (Always Free tier: request-based billing, min-instances=0).
# Usage: PROJECT_ID=my-project REGION=us-central1 ./deploy/cloudrun-deploy.sh
# Reads secrets/config from backend/.env (KEY=VALUE lines) and the service-account JSON file.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-proppulse-api}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/backend/.env}"

gcloud config set project "$PROJECT_ID" >/dev/null
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com cloudscheduler.googleapis.com calendar-json.googleapis.com

# Build a Cloud Run env-vars YAML from backend/.env (inlining the service-account JSON)
ENV_YAML="$(mktemp)"
trap 'rm -f "$ENV_YAML"' EXIT
python3 - "$ENV_FILE" "$ENV_YAML" "$ROOT/backend" <<'PY'
import json, os, sys
env_file, out, backend = sys.argv[1:]
values = {}
for line in open(env_file):
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    values[key.strip()] = value.strip().strip('"').strip("'")
sa = values.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
if sa and not sa.lstrip().startswith("{"):
    path = sa if os.path.isabs(sa) else os.path.join(backend, sa)
    values["GOOGLE_SERVICE_ACCOUNT_JSON"] = json.dumps(json.load(open(path)))
with open(out, "w") as fh:
    for key, value in values.items():
        fh.write(f"{key}: {json.dumps(value)}\n")
PY

gcloud run deploy "$SERVICE" \
  --source "$ROOT/backend" \
  --region "$REGION" \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances 2 \
  --memory 512Mi \
  --cpu 1 \
  --timeout 120 \
  --env-vars-file "$ENV_YAML"

URL="$(gcloud run services describe "$SERVICE" --region "$REGION" --format 'value(status.url)')"
echo
echo "Backend deployed: $URL"
echo "Next:"
echo "  ./deploy/set-telegram-webhook.sh $URL"
echo "  PROJECT_ID=$PROJECT_ID REGION=$REGION ./deploy/scheduler.sh $URL"
echo "  (set FRONTEND_ORIGIN in backend/.env to your dashboard URL and redeploy)"
