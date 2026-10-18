"""In-memory stand-ins for Supabase, Gemini, Telegram, Calendar and Resend."""

from __future__ import annotations

import itertools
import uuid
from datetime import date, datetime
from types import SimpleNamespace

from google.genai import types

from app.config import Settings
from app.db import _jsonable

_ids = itertools.count(1)


def make_settings(**overrides) -> Settings:
    base = dict(
        company_name="Acme Homes",
        agent_name="Liya",
        timezone="Africa/Addis_Ababa",
        currency="ETB",
        business_hours_start=9,
        business_hours_end=17,
        working_days="0,1,2,3,4,5",
        telegram_channel_id="@acme",
    )
    base.update(overrides)
    return Settings(_env_file=None, **base)


class FakeRepo:
    def __init__(self):
        self.clients: dict[str, dict] = {}
        self.properties: dict[str, dict] = {}
        self.messages: list[dict] = []
        self.appointments: dict[str, dict] = {}
        self.contracts: dict[str, dict] = {}
        self.installments: dict[str, dict] = {}
        self.announcements: list[dict] = []
        self.activity: list[dict] = []

    # helpers
    def _new(self, table: dict, data: dict, **defaults) -> dict:
        row = {"id": str(uuid.uuid4()), **defaults, **_jsonable(data)}
        table[row["id"]] = row
        return dict(row)

    # clients
    def get_client(self, client_id):
        return dict(self.clients[client_id]) if client_id in self.clients else None

    def get_client_by_telegram(self, chat_id):
        return next((dict(c) for c in self.clients.values() if c.get("telegram_chat_id") == chat_id), None)

    def get_client_by_web_session(self, session_id):
        return next((dict(c) for c in self.clients.values() if c.get("web_session_id") == session_id), None)

    def create_client(self, data):
        return self._new(self.clients, data, status="LEAD")

    def update_client(self, client_id, data):
        self.clients[client_id].update(_jsonable(data))
        return dict(self.clients[client_id])

    def list_clients(self, status=None, q=None):
        return [dict(c) for c in self.clients.values() if not status or c.get("status") == status]

    # messages
    def add_message(self, client_id, role, content, channel):
        self.messages.append({"id": next(_ids), "client_id": client_id, "role": role, "content": content, "channel": channel})

    def recent_messages(self, client_id, limit=20, roles=None):
        rows = [m for m in self.messages if m["client_id"] == client_id and (not roles or m["role"] in roles)]
        return rows[-limit:]

    # properties
    def list_properties(self, available_only=False):
        return [dict(p) for p in self.properties.values() if not available_only or p.get("status") != "SOLD_OUT"]

    def get_property(self, property_id):
        return dict(self.properties[property_id]) if property_id in self.properties else None

    def find_property_by_name(self, name):
        return next((dict(p) for p in self.properties.values() if p["name"].lower() == name.lower()), None)

    def insert_property(self, data):
        return self._new(self.properties, data, status="AVAILABLE")

    def update_property(self, property_id, data):
        self.properties[property_id].update(_jsonable(data))
        return dict(self.properties[property_id])

    # appointments
    def create_appointment(self, data):
        return self._new(self.appointments, data, status="SCHEDULED", reminder_sent_at=None)

    def update_appointment(self, appointment_id, data):
        self.appointments[appointment_id].update(_jsonable(data))
        return dict(self.appointments[appointment_id])

    def list_appointments(self, start_from=None, start_to=None, client_id=None):
        out = []
        for a in sorted(self.appointments.values(), key=lambda a: a["start_at"]):
            start = datetime.fromisoformat(a["start_at"])
            if start_from and start < start_from or start_to and start > start_to:
                continue
            if client_id and a["client_id"] != client_id:
                continue
            out.append({**a, "clients": self.get_client(a["client_id"]), "properties": self.get_property(a.get("property_id"))})
        return out

    # ledger
    def create_contract(self, data):
        return self._new(self.contracts, data)

    def create_installments(self, rows):
        return [self._new(self.installments, r, status="PENDING", last_reminded_at=None) for r in rows]

    def list_contracts(self, client_id=None):
        out = []
        for c in self.contracts.values():
            if client_id and c["client_id"] != client_id:
                continue
            insts = sorted((i for i in self.installments.values() if i["contract_id"] == c["id"]), key=lambda i: i["sequence_no"])
            out.append({**c, "clients": self.get_client(c["client_id"]), "properties": self.get_property(c.get("property_id")), "installments": insts})
        return out

    def pending_installments_due_by(self, due_by: date):
        out = []
        for i in sorted(self.installments.values(), key=lambda i: i["due_date"]):
            if i["status"] != "PENDING" or date.fromisoformat(i["due_date"]) > due_by:
                continue
            c = self.contracts[i["contract_id"]]
            out.append({**i, "contracts": {**c, "clients": self.get_client(c["client_id"]), "properties": self.get_property(c.get("property_id"))}})
        return out

    def update_installment(self, installment_id, data):
        self.installments[installment_id].update(_jsonable(data))
        return dict(self.installments[installment_id])

    # announcements & activity
    def create_announcement(self, data):
        row = {"id": str(uuid.uuid4()), **_jsonable(data)}
        self.announcements.append(row)
        return row

    def count(self, table, **filters):
        rows = {"clients": self.clients, "properties": self.properties}.get(table, {}).values()
        if table == "announcements":
            rows = self.announcements
        return sum(1 for r in rows if all(r.get(k) == v for k, v in filters.items()))

    def list_announcements(self, limit=50):
        return self.announcements[-limit:]

    def list_activity(self, limit=50, kind=None, after_id=None):
        return [a for a in self.activity if not kind or a["kind"] == kind][-limit:]

    def log_activity(self, kind, summary, payload=None, client_id=None):
        self.activity.append({"kind": kind, "summary": summary, "payload": payload, "client_id": client_id})


def function_call_response(*calls: tuple[str, dict]) -> types.GenerateContentResponse:
    parts = [types.Part(function_call=types.FunctionCall(name=name, args=args)) for name, args in calls]
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=parts))])


def text_response(text: str) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=[types.Part.from_text(text=text)]))]
    )


class FakeGemini:
    def __init__(self, scripted: list | None = None, text_reply: str = "generated text"):
        self.scripted = list(scripted or [])
        self.text_reply = text_reply
        self.requests: list = []

    def generate(self, contents, config):
        self.requests.append((list(contents), config))
        return self.scripted.pop(0)

    def text(self, prompt, system=None, temperature=0.7):
        self.requests.append((prompt, system))
        return self.text_reply

    def structured(self, prompt, schema, system=None):
        return self.scripted.pop(0)


class FakeTelegram:
    bot_username = "acme_bot"

    def __init__(self):
        self.sent: list[dict] = []
        self.channel_posts: list[dict] = []
        self.locations: list[tuple] = []

    def deep_link(self, payload):
        return f"https://t.me/{self.bot_username}?start={payload}"

    def send_message(self, chat_id, text, buttons=None):
        self.sent.append({"chat_id": chat_id, "text": text, "buttons": buttons})
        return {"message_id": len(self.sent)}

    def send_photo(self, chat_id, photo_url, caption, buttons=None):
        self.sent.append({"chat_id": chat_id, "photo_url": photo_url, "text": caption, "buttons": buttons})
        return {"message_id": len(self.sent)}

    def send_location(self, chat_id, lat, lng):
        self.locations.append((chat_id, lat, lng))

    def send_typing(self, chat_id):
        pass

    def answer_callback(self, *_args, **_kwargs):
        pass

    def post_to_channel(self, text, buttons=None, photo_url=None):
        self.channel_posts.append({"text": text, "buttons": buttons, "photo_url": photo_url})
        return {"message_id": 1000 + len(self.channel_posts)}


class FakeCalendar:
    def __init__(self, busy=None):
        self.busy = list(busy or [])
        self.events: list[dict] = []

    def busy_blocks(self, start, end):
        return [b for b in self.busy if b[0] < end and start < b[1]]

    def create_event(self, summary, description, start, end, location):
        self.events.append({"summary": summary, "start": start, "end": end, "location": location})
        self.busy.append((start, end))
        return {"id": f"evt{len(self.events)}"}


class FakeMailer:
    def __init__(self):
        self.sent: list[dict] = []

    def send(self, to, subject, title, body_html):
        self.sent.append({"to": to, "subject": subject, "title": title, "html": body_html})
        return "email-id"


def make_services(**overrides) -> SimpleNamespace:
    services = SimpleNamespace(
        settings=make_settings(),
        repo=FakeRepo(),
        gemini=FakeGemini(),
        telegram=FakeTelegram(),
        calendar=FakeCalendar(),
        mailer=FakeMailer(),
    )
    for key, value in overrides.items():
        setattr(services, key, value)
    return services
