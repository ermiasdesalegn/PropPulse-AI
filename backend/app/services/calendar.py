"""Google Calendar via a service account: free-slot search + event creation."""

from __future__ import annotations

import json
import os
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]

SLOT_MINUTES = {"PHONE_CALL": 30, "SITE_VISIT": 60}


def load_service_account_info(value: str) -> dict:
    value = value.strip()
    if value.startswith("{"):
        return json.loads(value)
    with open(os.path.expanduser(value), encoding="utf-8") as fh:
        return json.load(fh)


def compute_free_slots(
    day_from: date,
    day_to: date,
    busy: list[tuple[datetime, datetime]],
    tz: ZoneInfo,
    hours: tuple[int, int],
    working_days: set[int],
    slot_minutes: int,
    now: datetime,
    min_lead: timedelta = timedelta(hours=1),
    limit: int = 12,
) -> list[datetime]:
    """Return slot start times (tz-aware) inside business hours that don't overlap any busy block."""
    slots: list[datetime] = []
    step = timedelta(minutes=slot_minutes)
    earliest = now + min_lead
    day = day_from
    while day <= day_to and len(slots) < limit:
        if day.weekday() in working_days:
            cursor = datetime.combine(day, time(hours[0]), tz)
            day_end = datetime.combine(day, time(hours[1]), tz)
            while cursor + step <= day_end and len(slots) < limit:
                end = cursor + step
                if cursor >= earliest and not any(b0 < end and cursor < b1 for b0, b1 in busy):
                    slots.append(cursor)
                cursor = end
        day += timedelta(days=1)
    return slots


class Calendar:
    def __init__(self, service_account_json: str, calendar_id: str, tz: ZoneInfo):
        credentials = service_account.Credentials.from_service_account_info(
            load_service_account_info(service_account_json), scopes=SCOPES
        )
        self.service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
        self.calendar_id = calendar_id
        self.tz = tz

    def busy_blocks(self, start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
        body = {
            "timeMin": start.isoformat(),
            "timeMax": end.isoformat(),
            "timeZone": str(self.tz),
            "items": [{"id": self.calendar_id}],
        }
        result = self.service.freebusy().query(body=body).execute()
        calendar = result["calendars"].get(self.calendar_id, {})
        if calendar.get("errors"):
            raise RuntimeError(f"Calendar freebusy error: {calendar['errors']}")
        return [
            (datetime.fromisoformat(b["start"]), datetime.fromisoformat(b["end"]))
            for b in calendar.get("busy", [])
        ]

    def create_event(self, summary: str, description: str, start: datetime, end: datetime, location: str | None) -> dict:
        body = {
            "summary": summary,
            "description": description,
            "location": location,
            "start": {"dateTime": start.isoformat(), "timeZone": str(self.tz)},
            "end": {"dateTime": end.isoformat(), "timeZone": str(self.tz)},
            "reminders": {"useDefault": True},
        }
        return self.service.events().insert(calendarId=self.calendar_id, body=body).execute()
