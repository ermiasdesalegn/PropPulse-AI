from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Security
    admin_api_key: str = ""
    cron_secret: str = ""
    ingest_webhook_secret: str = ""
    telegram_webhook_secret: str = ""
    frontend_origin: str = "http://localhost:3000"

    # Gemini
    gemini_api_key: str = ""
    gemini_api_keys: str = ""
    gemini_keys_file: str = "keys.csv"
    gemini_model: str = "gemini-3.8-flash"

    # Supabase
    supabase_url: str = ""
    supabase_service_role_key: str = ""

    # Telegram
    telegram_bot_token: str = ""
    telegram_channel_id: str = ""

    # Google Calendar
    google_service_account_json: str = ""
    google_calendar_id: str = ""

    # Resend
    resend_api_key: str = ""
    email_from: str = "PropPulse AI <onboarding@resend.dev>"

    # Demo Fallbacks (for evaluators / sandbox free-tier delivery)
    demo_fallback_telegram_chat_id: str = ""
    demo_fallback_email: str = ""

    # Business
    company_name: str = "PropPulse Developments"
    agent_name: str = "Liya"
    timezone: str = "Africa/Addis_Ababa"
    currency: str = "ETB"
    business_hours_start: int = 9
    business_hours_end: int = 17
    working_days: str = "0,1,2,3,4,5"
    sales_office_address: str = "Bole Road, Addis Ababa"

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def working_weekdays(self) -> set[int]:
        return {int(d) for d in self.working_days.split(",") if d.strip()}

    def get_gemini_api_keys(self) -> list[str]:
        from pathlib import Path
        from app.services.gemini import load_keys_from_file

        keys: list[str] = []
        # 1. Prioritize CSV / keys file
        if self.gemini_keys_file:
            candidate_paths = [
                Path(self.gemini_keys_file),
                Path(__file__).resolve().parent.parent / self.gemini_keys_file,
                Path(__file__).resolve().parent.parent.parent / self.gemini_keys_file,
            ]
            for candidate in candidate_paths:
                if candidate.is_file():
                    for k in load_keys_from_file(candidate):
                        if k not in keys:
                            keys.append(k)
                    if keys:
                        break

        # 2. Fall back to environment variables only if no keys loaded from file
        if not keys:
            if self.gemini_api_keys:
                keys.extend([k.strip() for k in self.gemini_api_keys.split(",") if k.strip()])
            if self.gemini_api_key and self.gemini_api_key.strip():
                k = self.gemini_api_key.strip()
                if k not in keys:
                    keys.append(k)

        return keys


@lru_cache
def get_settings() -> Settings:
    return Settings()
