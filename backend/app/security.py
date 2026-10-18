import hmac

from fastapi import Header, HTTPException, Query

from app.config import get_settings


def _matches(expected: str, provided: str | None) -> bool:
    return bool(provided) and hmac.compare_digest(expected, provided)


def require_admin(x_admin_key: str | None = Header(default=None)) -> None:
    expected = get_settings().admin_api_key
    if expected and not _matches(expected, x_admin_key):
        raise HTTPException(status_code=401, detail="Invalid admin key")


def require_cron(
    x_cron_secret: str | None = Header(default=None), x_admin_key: str | None = Header(default=None)
) -> None:
    settings = get_settings()
    if settings.cron_secret and _matches(settings.cron_secret, x_cron_secret):
        return
    if settings.admin_api_key and _matches(settings.admin_api_key, x_admin_key):
        return
    if not settings.cron_secret and not settings.admin_api_key:
        return
    raise HTTPException(status_code=401, detail="Invalid cron secret")


def require_ingest_token(token: str | None = Query(default=None)) -> None:
    expected = get_settings().ingest_webhook_secret
    if expected and not _matches(expected, token):
        raise HTTPException(status_code=401, detail="Invalid ingest token")


def require_telegram_secret(x_telegram_bot_api_secret_token: str | None = Header(default=None)) -> None:
    expected = get_settings().telegram_webhook_secret
    if expected and not _matches(expected, x_telegram_bot_api_secret_token):
        raise HTTPException(status_code=401, detail="Invalid Telegram secret")
