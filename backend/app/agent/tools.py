"""Gemini function-calling tools: declarations + implementations."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Callable

from google.genai import types

from app.notify import fmt_dt, money, notify_client, record
from app.services.calendar import SLOT_MINUTES, compute_free_slots
from app.services.email import details_table, paragraphs

log = logging.getLogger(__name__)

MAX_AVAILABILITY_DAYS = 14
LONGEST_SLOT = timedelta(minutes=max(SLOT_MINUTES.values()))
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class AgentContext:
    services: Any
    client: dict
    channel: str  # "telegram" | "web"
    now: datetime | None = None
    tool_log: list[dict] = field(default_factory=list)

    @property
    def settings(self):
        return self.services.settings

    def current_time(self) -> datetime:
        return self.now or datetime.now(self.settings.tz)


# ---------------------------------------------------------------------------
# Declarations
# ---------------------------------------------------------------------------
DECLARATIONS = [
    types.FunctionDeclaration(
        name="search_properties",
        description=(
            "Search the live property inventory. Use for ANY question about available units, prices, "
            "floor plans, sizes, down payments, payment plans or construction status. Omit filters you don't know."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "location": {"type": "STRING", "description": "Neighbourhood / area, e.g. 'Bole'"},
                "max_price": {"type": "NUMBER", "description": "Maximum total price"},
                "min_price": {"type": "NUMBER", "description": "Minimum total price"},
                "bedrooms": {"type": "INTEGER", "description": "Exact number of bedrooms"},
                "query": {"type": "STRING", "description": "Free-text keywords, e.g. property name or 'garden'"},
            },
        },
    ),
    types.FunctionDeclaration(
        name="upsert_client_profile",
        description=(
            "Save details the client has shared about themselves into the CRM phonebook. Call it as soon as the "
            "client mentions any of these fields — only include fields the client actually stated."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "full_name": {"type": "STRING"},
                "phone": {"type": "STRING"},
                "email": {"type": "STRING"},
                "budget_min": {"type": "NUMBER"},
                "budget_max": {"type": "NUMBER"},
                "preferred_location": {"type": "STRING"},
                "preferred_bedrooms": {"type": "INTEGER"},
                "interested_property_id": {"type": "STRING", "description": "id from search_properties"},
                "notes": {"type": "STRING", "description": "Other useful context (family size, timeline, ...)"},
            },
        },
    ),
    types.FunctionDeclaration(
        name="check_calendar_availability",
        description="List free time slots for a phone consultation or an in-person site visit.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "date_from": {"type": "STRING", "description": "YYYY-MM-DD (local date)"},
                "date_to": {"type": "STRING", "description": "YYYY-MM-DD (local date), max 14 days after date_from"},
                "appointment_type": {"type": "STRING", "enum": ["PHONE_CALL", "SITE_VISIT"]},
            },
            "required": ["date_from", "appointment_type"],
        },
    ),
    types.FunctionDeclaration(
        name="book_appointment",
        description=(
            "Book a confirmed slot (from check_calendar_availability) after the client explicitly agrees. "
            "Creates the calendar event and sends Telegram + email confirmations."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "start_iso": {"type": "STRING", "description": "Slot start, ISO-8601 with offset, as returned"},
                "appointment_type": {"type": "STRING", "enum": ["PHONE_CALL", "SITE_VISIT"]},
                "property_id": {"type": "STRING", "description": "Required for SITE_VISIT"},
                "notes": {"type": "STRING"},
            },
            "required": ["start_iso", "appointment_type"],
        },
    ),
]

TOOL = types.Tool(function_declarations=DECLARATIONS)


# ---------------------------------------------------------------------------
# search_properties
# ---------------------------------------------------------------------------
def property_summary(p: dict, currency: str) -> dict:
    return {
        "id": p["id"],
        "name": p["name"],
        "location": p.get("location"),
        "price": money(p.get("price"), currency),
        "price_value": p.get("price"),
        "price_per_sqm": money(p.get("price_per_sqm"), currency) if p.get("price_per_sqm") else None,
        "bedrooms": p.get("bedrooms"),
        "area_sqm": p.get("area_sqm"),
        "down_payment": p.get("down_payment"),
        "payment_plan": p.get("payment_plan"),
        "construction_status": p.get("construction_status"),
        "description": p.get("description"),
        "floor_plan_url": p.get("floor_plan_url"),
        "status": p.get("status"),
    }


def filter_properties(
    props: list[dict],
    location: str | None = None,
    max_price: float | None = None,
    min_price: float | None = None,
    bedrooms: int | None = None,
    query: str | None = None,
) -> list[dict]:
    def ok(p: dict) -> bool:
        price = float(p["price"]) if p.get("price") is not None else None
        if location and location.lower() not in (p.get("location") or "").lower():
            return False
        if max_price is not None and (price is None or price > max_price):
            return False
        if min_price is not None and (price is None or price < min_price):
            return False
        if bedrooms is not None and p.get("bedrooms") != bedrooms:
            return False
        if query:
            haystack = " ".join(str(p.get(k) or "") for k in ("name", "location", "description", "payment_plan")).lower()
            words = [w for w in re.findall(r"\w+", query.lower()) if len(w) > 2]
            if words and not any(w in haystack for w in words):
                return False
        return True

    return [p for p in props if ok(p)]


def search_properties(ctx: AgentContext, **args: Any) -> dict:
    props = ctx.services.repo.list_properties(available_only=True)
    currency = ctx.settings.currency
    matches = filter_properties(
        props,
        location=args.get("location"),
        max_price=args.get("max_price"),
        min_price=args.get("min_price"),
        bedrooms=int(args["bedrooms"]) if args.get("bedrooms") is not None else None,
        query=args.get("query"),
    )
    result: dict[str, Any] = {"results": [property_summary(p, currency) for p in matches[:6]]}
    if not matches and props:
        target = args.get("max_price") or args.get("min_price")
        if target:
            props = sorted(props, key=lambda p: abs(float(p.get("price") or 0) - float(target)))
        result["closest_alternatives"] = [property_summary(p, currency) for p in props[:3]]
    return result


# ---------------------------------------------------------------------------
# upsert_client_profile
# ---------------------------------------------------------------------------
PROFILE_FIELDS = (
    "full_name",
    "phone",
    "email",
    "budget_min",
    "budget_max",
    "preferred_location",
    "preferred_bedrooms",
    "interested_property_id",
    "notes",
)


def is_qualified(client: dict) -> bool:
    has_contact = bool(client.get("phone") or client.get("email"))
    has_budget = client.get("budget_max") is not None or client.get("budget_min") is not None
    return bool(client.get("full_name")) and has_contact and has_budget


def missing_profile_fields(client: dict) -> list[str]:
    missing = []
    if not client.get("full_name"):
        missing.append("full_name")
    if not (client.get("phone") or client.get("email")):
        missing.append("phone or email")
    if client.get("budget_max") is None and client.get("budget_min") is None:
        missing.append("budget")
    if not client.get("preferred_location"):
        missing.append("preferred_location")
    if client.get("preferred_bedrooms") is None:
        missing.append("preferred_bedrooms")
    return missing


def upsert_client_profile(ctx: AgentContext, **args: Any) -> dict:
    update: dict[str, Any] = {}
    for key in PROFILE_FIELDS:
        value = args.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        update[key] = value.strip() if isinstance(value, str) else value

    if "email" in update and not EMAIL_RE.match(update["email"]):
        return {"error": f"'{update['email']}' doesn't look like a valid email — ask the client to re-check it."}
    if "preferred_bedrooms" in update:
        update["preferred_bedrooms"] = int(update["preferred_bedrooms"])
    if "interested_property_id" in update and not ctx.services.repo.get_property(update["interested_property_id"]):
        update.pop("interested_property_id")
    if "notes" in update and ctx.client.get("notes"):
        update["notes"] = f"{ctx.client['notes']}\n{update['notes']}"

    merged = {**ctx.client, **update}
    if merged.get("status") == "LEAD" and is_qualified(merged):
        update["status"] = "QUALIFIED"

    if update:
        ctx.client.update(ctx.services.repo.update_client(ctx.client["id"], update))
        record(
            ctx.services,
            "crm_update",
            f"Updated profile for {ctx.client.get('full_name') or 'lead'}: {', '.join(k for k in update if k != 'notes') or 'notes'}",
            {"fields": update},
            ctx.client["id"],
        )
    return {
        "saved_fields": sorted(update),
        "status": ctx.client.get("status"),
        "still_missing": missing_profile_fields(ctx.client),
    }


# ---------------------------------------------------------------------------
# Calendar tools
# ---------------------------------------------------------------------------
def _busy(ctx: AgentContext, start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    blocks: list[tuple[datetime, datetime]] = []
    try:
        blocks.extend(ctx.services.calendar.busy_blocks(start, end))
    except Exception as exc:  # calendar unavailable → fall back to DB appointments only
        log.warning("calendar freebusy unavailable: %s", exc)
    # look back by the longest slot so meetings that started earlier but overlap are included
    for appt in ctx.services.repo.list_appointments(start - LONGEST_SLOT, end):
        if appt.get("status") == "SCHEDULED":
            blocks.append((datetime.fromisoformat(appt["start_at"]), datetime.fromisoformat(appt["end_at"])))
    return blocks


def _free_slots(ctx: AgentContext, day_from: date, day_to: date, appt_type: str) -> list[datetime]:
    tz = ctx.settings.tz
    start = datetime.combine(day_from, datetime.min.time(), tz)
    end = datetime.combine(day_to + timedelta(days=1), datetime.min.time(), tz)
    return compute_free_slots(
        day_from,
        day_to,
        _busy(ctx, start, end),
        tz,
        (ctx.settings.business_hours_start, ctx.settings.business_hours_end),
        ctx.settings.working_weekdays,
        SLOT_MINUTES[appt_type],
        ctx.current_time(),
    )


def check_calendar_availability(ctx: AgentContext, **args: Any) -> dict:
    appt_type = args.get("appointment_type", "SITE_VISIT")
    if appt_type not in SLOT_MINUTES:
        return {"error": "appointment_type must be PHONE_CALL or SITE_VISIT"}
    today = ctx.current_time().date()
    try:
        day_from = max(date.fromisoformat(args["date_from"]), today)
        day_to = date.fromisoformat(args["date_to"]) if args.get("date_to") else day_from + timedelta(days=3)
    except (KeyError, ValueError):
        return {"error": "Dates must be YYYY-MM-DD"}
    day_to = min(max(day_to, day_from), day_from + timedelta(days=MAX_AVAILABILITY_DAYS))

    slots = _free_slots(ctx, day_from, day_to, appt_type)
    tz = ctx.settings.tz
    return {
        "appointment_type": appt_type,
        "duration_minutes": SLOT_MINUTES[appt_type],
        "timezone": str(tz),
        "slots": [{"start_iso": s.isoformat(), "label": s.strftime("%a %d %b, %I:%M %p")} for s in slots],
        "note": "Offer the client 2-3 of these options." if slots else "No free slots in this range — try other dates.",
    }


def book_appointment(ctx: AgentContext, **args: Any) -> dict:
    services, settings, client = ctx.services, ctx.settings, ctx.client
    appt_type = args.get("appointment_type")
    if appt_type not in SLOT_MINUTES:
        return {"error": "appointment_type must be PHONE_CALL or SITE_VISIT"}
    if not client.get("full_name") or not (client.get("phone") or client.get("email")):
        return {"error": "Collect the client's full name and a phone number or email (save via upsert_client_profile) before booking."}

    try:
        start = datetime.fromisoformat(args["start_iso"])
    except (KeyError, ValueError):
        return {"error": "start_iso must be an ISO-8601 datetime from check_calendar_availability"}
    if start.tzinfo is None:
        start = start.replace(tzinfo=settings.tz)
    end = start + timedelta(minutes=SLOT_MINUTES[appt_type])
    if start <= ctx.current_time():
        return {"error": "That time is in the past. Check availability again."}

    if any(b0 < end and start < b1 for b0, b1 in _busy(ctx, start, end)):
        return {"error": "That slot was just taken. Call check_calendar_availability again and offer new options."}

    property_id = args.get("property_id") or client.get("interested_property_id")
    prop = services.repo.get_property(property_id) if property_id else None
    if appt_type == "SITE_VISIT" and not prop:
        return {"error": "A site visit needs a property_id (use search_properties and confirm which property)."}

    kind_label = "Site visit" if appt_type == "SITE_VISIT" else "Phone consultation"
    location = prop.get("location") if (prop and appt_type == "SITE_VISIT") else None
    title = f"{kind_label}: {client['full_name']}" + (f" — {prop['name']}" if prop else "")
    description = "\n".join(
        line
        for line in (
            f"Client: {client['full_name']}",
            f"Phone: {client.get('phone') or '—'}",
            f"Email: {client.get('email') or '—'}",
            f"Telegram: @{client['telegram_username']}" if client.get("telegram_username") else None,
            f"Budget: {money(client.get('budget_min'), settings.currency)} – {money(client.get('budget_max'), settings.currency)}",
            f"Property: {prop['name']}" if prop else None,
            f"Notes: {args['notes']}" if args.get("notes") else None,
            "Booked automatically by PropPulse AI.",
        )
        if line
    )

    event_id = None
    try:
        event_id = services.calendar.create_event(title, description, start, end, location).get("id")
    except Exception as exc:
        log.warning("calendar event creation failed: %s", exc)

    appointment = services.repo.create_appointment(
        {
            "client_id": client["id"],
            "property_id": prop["id"] if prop else None,
            "type": appt_type,
            "start_at": start,
            "end_at": end,
            "calendar_event_id": event_id,
            "notes": args.get("notes"),
        }
    )
    if client.get("status") != "CLOSED_BUYER":
        new_status = "SITE_VISIT_BOOKED" if appt_type == "SITE_VISIT" else ("QUALIFIED" if is_qualified(client) else client.get("status"))
        if new_status != client.get("status"):
            client.update(services.repo.update_client(client["id"], {"status": new_status}))

    when = fmt_dt(start, settings.tz)
    rows = [("What", kind_label), ("When", f"{when} ({settings.timezone})")]
    if prop:
        rows.append(("Property", prop["name"]))
    if appt_type == "SITE_VISIT":
        rows.append(("Where", prop.get("location") or settings.sales_office_address))
    else:
        rows.append(("How", f"We'll call you on {client.get('phone') or 'Telegram'}"))

    tg_text = "\n".join(
        [f"✅ {kind_label} confirmed", ""]
        + [f"{k}: {v}" for k, v in rows]
        + ["", "Reply here anytime if you need to reschedule."]
    )
    delivery = notify_client(
        services,
        client,
        text=tg_text,
        location=(prop.get("latitude"), prop.get("longitude")) if (prop and appt_type == "SITE_VISIT") else None,
        email_subject=f"Confirmed: {kind_label} on {when}",
        email_title=f"Your {kind_label.lower()} is confirmed",
        email_html=paragraphs(f"Hi {client['full_name']},\n\nThank you for your interest. Here are your booking details:")
        + details_table(rows)
        + paragraphs(f"If you need to reschedule, simply reply to our Telegram assistant.\n\n— {settings.agent_name}, {settings.company_name}"),
    )
    record(
        services,
        "appointment_booked",
        f"Booked {kind_label.lower()} for {client['full_name']} on {when}",
        {"appointment_id": appointment["id"], "calendar_synced": bool(event_id), "delivery": delivery},
        client["id"],
    )
    return {
        "booked": True,
        "appointment_id": appointment["id"],
        "when": when,
        "calendar_synced": bool(event_id),
        "confirmation_sent": delivery,
    }


IMPLEMENTATIONS: dict[str, Callable[..., dict]] = {
    "search_properties": search_properties,
    "upsert_client_profile": upsert_client_profile,
    "check_calendar_availability": check_calendar_availability,
    "book_appointment": book_appointment,
}


def execute_tool(ctx: AgentContext, name: str, args: dict) -> dict:
    impl = IMPLEMENTATIONS.get(name)
    if not impl:
        return {"error": f"Unknown tool {name}"}
    try:
        result = impl(ctx, **args)
    except Exception as exc:
        log.exception("tool %s failed", name)
        result = {"error": f"{name} failed: {exc}"}
    ctx.tool_log.append({"name": name, "args": args, "result": result})
    return result
