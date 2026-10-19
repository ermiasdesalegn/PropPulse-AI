"""Lazily-constructed service container shared by routers and workflows.

Workflows only touch `services.<attr>`, so tests can pass any object exposing the
same attributes (see tests/fakes.py).
"""

from __future__ import annotations

from functools import cached_property, lru_cache

from app.config import Settings, get_settings
from app.db import Repo
from app.services.calendar import Calendar
from app.services.email import Mailer
from app.services.gemini import Gemini
from app.services.telegram import Telegram


class NotConfigured(RuntimeError):
    pass


def _require(settings: Settings, *names: str) -> None:
    missing = [n.upper() for n in names if not getattr(settings, n)]
    if missing:
        raise NotConfigured(f"Missing configuration: {', '.join(missing)}")


class Services:
    def __init__(self, settings: Settings):
        self.settings = settings

    @cached_property
    def repo(self) -> Repo:
        _require(self.settings, "supabase_url", "supabase_service_role_key")
        return Repo(self.settings.supabase_url, self.settings.supabase_service_role_key)

    @cached_property
    def gemini(self) -> Gemini:
        keys = self.settings.get_gemini_api_keys()
        if not keys:
            _require(self.settings, "gemini_api_key")
        return Gemini(api_keys=keys, model=self.settings.gemini_model)

    @cached_property
    def telegram(self) -> Telegram:
        _require(self.settings, "telegram_bot_token")
        return Telegram(self.settings.telegram_bot_token, self.settings.telegram_channel_id)

    @cached_property
    def calendar(self) -> Calendar:
        _require(self.settings, "google_service_account_json", "google_calendar_id")
        return Calendar(self.settings.google_service_account_json, self.settings.google_calendar_id, self.settings.tz)

    @cached_property
    def mailer(self) -> Mailer:
        _require(self.settings, "resend_api_key")
        return Mailer(self.settings.resend_api_key, self.settings.email_from, self.settings.company_name)

    def integration_status(self) -> dict[str, bool]:
        s = self.settings
        gemini_ready = bool(s.get_gemini_api_keys() if hasattr(s, "get_gemini_api_keys") else s.gemini_api_key)
        return {
            "gemini": gemini_ready,
            "supabase": bool(s.supabase_url and s.supabase_service_role_key),
            "telegram": bool(s.telegram_bot_token),
            "telegram_channel": bool(s.telegram_channel_id),
            "calendar": bool(s.google_service_account_json and s.google_calendar_id),
            "email": bool(s.resend_api_key),
        }


@lru_cache
def get_services() -> Services:
    return Services(get_settings())
