import logging

from fastapi import APIRouter, Depends, Request

from app.deps import get_services
from app.security import require_telegram_secret
from app.workflows.conversation import handle_telegram_update

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/telegram", tags=["telegram"])


@router.post("/webhook", dependencies=[Depends(require_telegram_secret)])
def telegram_webhook(update: dict) -> dict:
    # Processed inline (not as a background task) so Cloud Run keeps CPU allocated for the whole turn.
    # Always 200 so Telegram doesn't redeliver a poison update forever.
    try:
        handle_telegram_update(get_services(), update)
    except Exception:
        log.exception("failed to handle telegram update %s", update.get("update_id"))
    return {"ok": True}


@router.post("/setup-webhook")
def setup_webhook(url: str) -> dict:
    """Register Telegram webhook URL for cloud deployments."""
    services = get_services()
    secret = services.settings.telegram_webhook_secret or None
    result = services.telegram.set_webhook(url, secret)
    return {"ok": True, "result": result}


@router.post("/delete-webhook")
def delete_webhook() -> dict:
    """Remove Telegram webhook to switch back to local polling."""
    services = get_services()
    result = services.telegram.delete_webhook()
    return {"ok": True, "result": result}
