#!/usr/bin/env bash
# Point the Telegram bot at the deployed backend.
# Usage: ./deploy/set-telegram-webhook.sh https://proppulse-api-xxxx.run.app
set -euo pipefail

BACKEND_URL="${1:?usage: set-telegram-webhook.sh <backend-url>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOKEN="${TELEGRAM_BOT_TOKEN:-$(grep -E '^TELEGRAM_BOT_TOKEN=' "$ROOT/backend/.env" | cut -d= -f2-)}"
SECRET="${TELEGRAM_WEBHOOK_SECRET:-$(grep -E '^TELEGRAM_WEBHOOK_SECRET=' "$ROOT/backend/.env" | cut -d= -f2-)}"

curl -sS "https://api.telegram.org/bot${TOKEN}/setWebhook" \
  -H 'Content-Type: application/json' \
  -d "{\"url\": \"${BACKEND_URL%/}/api/telegram/webhook\", \"secret_token\": \"${SECRET}\", \"allowed_updates\": [\"message\", \"callback_query\"]}"
echo
curl -sS "https://api.telegram.org/bot${TOKEN}/getWebhookInfo"
echo
